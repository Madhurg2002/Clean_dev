import sys
import time
from pathlib import Path
from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.data_structures import Point
from src.fs_utils import format_size

TUI_STYLE = Style.from_dict({
    "help": "fg:#888888 italic",
    "search_label": "fg:#00ffff bold",
    "search_query": "fg:#ffffff bold",
    "status": "fg:#ffaa00 bold",
    "group_header": "fg:#ff55ff bold",
    "item_highlighted": "bg:#333333 fg:#ffffff",
    "checkbox_checked": "fg:#00ff00 bold",
    "checkbox_unchecked": "fg:#555555",
    "item_type": "fg:#00ffff",
    "item_size": "fg:#5555ff bold",
    "item_path": "fg:#cccccc",
    "pointer": "fg:#ffaa00 bold",
})

class FilterableCheckboxApp:
    def __init__(self, items: list, group_by_folder: bool):
        self.all_items = items
        self.group_by_folder = group_by_folder
        self.filter_query = ""
        self.selected_paths = set()  # set of str(item["long_path"])
        self.current_index = 0  # index in self.filtered_items
        self.filtered_items = []
        self.highlighted_line_y = 0
        self.confirmed = False

        # Pre-calculate initial filtered list
        self.update_filtered_list()

    def update_filtered_list(self):
        query = self.filter_query.lower().strip()
        if not query:
            self.filtered_items = self.all_items.copy()
        else:
            self.filtered_items = [
                item for item in self.all_items
                if query in item["type"].lower()
                or query in str(item["path"]).lower()
                or query in format_size(item["size"]).lower()
            ]
        
        # Clamp cursor index
        if not self.filtered_items:
            self.current_index = 0
        elif self.current_index >= len(self.filtered_items):
            self.current_index = len(self.filtered_items) - 1

    def get_grouped_entries(self):
        """
        Groups self.filtered_items and returns a list of display tuples:
        [('header', 'Group Title'), ('item', item_dict, index_in_filtered_list)]
        """
        if not self.filtered_items:
            return []

        # 1. Group items
        groups = {}
        for idx, item in enumerate(self.filtered_items):
            if self.group_by_folder:
                group_key = str(Path(item["path"]).parent)
            else:
                group_key = item["type"]
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append((item, idx))

        # 2. Sort groups
        sorted_group_keys = sorted(groups.keys(), key=lambda x: x.lower())

        # 3. Flatten into display entries
        entries = []
        for g_key in sorted_group_keys:
            entries.append(('header', g_key))
            # Sort items in group by size descending
            group_items = sorted(groups[g_key], key=lambda x: x[0]["size"], reverse=True)
            for item, idx in group_items:
                entries.append(('item', item, idx))

        return entries

    def get_lines(self):
        entries = self.get_grouped_entries()
        fragments = []
        self.highlighted_line_y = 0
        current_y = 0

        if not entries:
            fragments.append(("", "\n"))
            fragments.append(("class:help", "  (No items match the filter query)\n"))
            return fragments

        for entry_type, *data in entries:
            if entry_type == 'header':
                g_title = data[0]
                fragments.append(("class:group_header", f"\n--- {g_title} ---\n"))
                current_y += 2  # Newline + header line
            elif entry_type == 'item':
                item, idx = data[0], data[1]
                is_selected = str(item["long_path"]) in self.selected_paths
                is_hovered = idx == self.current_index

                if is_hovered:
                    self.highlighted_line_y = current_y
                    style_prefix = "class:item_highlighted"
                    pointer_frag = ("class:pointer", " > ")
                else:
                    style_prefix = ""
                    pointer_frag = ("", "   ")

                cb_style = "class:checkbox_checked" if is_selected else "class:checkbox_unchecked"
                cb_char = "[x]" if is_selected else "[ ]"

                fragments.extend([
                    pointer_frag,
                    (f"{style_prefix} {cb_style}", f"{cb_char} "),
                    (f"{style_prefix} class:item_type", f"{item['type']:<14}"),
                    (f"{style_prefix}", " | "),
                    (f"{style_prefix} class:item_size", f"{format_size(item['size']):<10}"),
                    (f"{style_prefix}", " | "),
                    (f"{style_prefix} class:item_path", f"{item['path']}\n")
                ])
                current_y += 1

        return fragments

    def run(self):
        # Header/Help
        header_text = (
            "Filter: (start typing to search) | Up/Down: navigate | Space: toggle (auto-moves down)\n"
            "Enter: confirm selection | Ctrl+U: clear filter | Ctrl+C: abort"
        )
        header_window = Window(
            FormattedTextControl(lambda: [("class:help", header_text)]),
            height=2,
            char_style="class:help"
        )

        # Search Bar
        def get_search_text():
            return [
                ("class:search_label", "🔍 Filter: "),
                ("class:search_query", self.filter_query),
                ("class:search_query", "_" if int(time.time() * 2) % 2 == 0 else " ")  # flashing cursor
            ]
        search_window = Window(
            FormattedTextControl(get_search_text),
            height=1
        )

        # Status Bar
        def get_status_text():
            # Calculate metrics
            total_reclaimable = sum(item["size"] for item in self.all_items)
            selected_items = [item for item in self.all_items if str(item["long_path"]) in self.selected_paths]
            selected_size = sum(item["size"] for item in selected_items)
            
            return [
                ("class:status", f"Total Recovery: {format_size(total_reclaimable)} | "),
                ("class:status", f"Selected: {format_size(selected_size)} ({len(selected_items)} of {len(self.all_items)} items)")
            ]
        status_window = Window(
            FormattedTextControl(get_status_text),
            height=1
        )

        # Divider
        divider_window = Window(
            FormattedTextControl(lambda: [("", "-" * 80 + "\n")]),
            height=1
        )

        # List Window
        list_control = FormattedTextControl(
            self.get_lines,
            get_cursor_position=lambda: Point(0, self.highlighted_line_y)
        )
        list_window = Window(list_control)

        # Define key bindings
        kb = KeyBindings()

        @kb.add("up")
        @kb.add("k")
        def _(event):
            if self.filtered_items:
                self.current_index = max(0, self.current_index - 1)

        @kb.add("down")
        @kb.add("j")
        def _(event):
            if self.filtered_items:
                self.current_index = min(len(self.filtered_items) - 1, self.current_index + 1)

        @kb.add("space")
        def _(event):
            if self.filtered_items:
                item = self.filtered_items[self.current_index]
                path_str = str(item["long_path"])
                if path_str in self.selected_paths:
                    self.selected_paths.remove(path_str)
                else:
                    self.selected_paths.add(path_str)
                
                # Auto-move pointer to next item
                self.current_index = min(len(self.filtered_items) - 1, self.current_index + 1)

        @kb.add("backspace")
        def _(event):
            if self.filter_query:
                self.filter_query = self.filter_query[:-1]
                self.update_filtered_list()

        @kb.add("c-u")
        def _(event):
            self.filter_query = ""
            self.update_filtered_list()

        @kb.add("enter")
        def _(event):
            self.confirmed = True
            event.app.exit()

        @kb.add("c-c")
        @kb.add("escape")
        def _(event):
            self.confirmed = False
            event.app.exit()

        # Catch-all for typing printable characters
        @kb.add("<any>")
        def _(event):
            # event.data holds the string of key presses
            for char in event.data:
                if char.isprintable():
                    self.filter_query += char
                    self.update_filtered_list()

        # Build application layout
        layout = Layout(HSplit([
            header_window,
            search_window,
            status_window,
            divider_window,
            list_window
        ]))

        app = Application(
            layout=layout,
            key_bindings=kb,
            style=TUI_STYLE,
            full_screen=True
        )

        app.run()

        if self.confirmed:
            # Return list of selected items
            return [item for item in self.all_items if str(item["long_path"]) in self.selected_paths]
        return None

def filter_checkbox_tui(items: list, group_by_folder: bool) -> list:
    """
    Launches the custom filterable checkbox TUI.
    Returns the selected items list on confirm, or None on cancel/abort.
    """
    app = FilterableCheckboxApp(items, group_by_folder)
    return app.run()
