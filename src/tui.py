import sys
import time
from pathlib import Path
from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
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

def get_target_descendants(node):
    targets = []
    if node["is_target"]:
        targets.append(node["item"][0])  # node["item"] is (item_dict, index)
    for child in node["children"].values():
        targets.extend(get_target_descendants(child))
    return targets

def get_folder_cb_state(node, selected_paths):
    descendants = get_target_descendants(node)
    if not descendants:
        return "unchecked"
    checked_count = sum(1 for item in descendants if str(item["long_path"]) in selected_paths)
    if checked_count == 0:
        return "unchecked"
    elif checked_count == len(descendants):
        return "checked"
    else:
        return "partial"

class FilterableCheckboxApp:
    def __init__(self, items: list, group_by_folder: bool, root_path: Path):
        self.all_items = items
        self.group_by_folder = group_by_folder
        self.root_path = root_path
        self.filter_query = ""
        self.selected_paths = set()  # set of str(item["long_path"])
        self.current_index = 0  # index in self.visible_lines
        self.filtered_items = []
        self.visible_lines = []
        self.folder_expanded = {}  # str(path) -> bool (default: True)
        self.highlighted_line_y = 0
        self.confirmed = False
        self.mode = "filter"

        # Pre-calculate initial list
        self.update_filtered_list()

    def is_selectable(self, line):
        return line["type"] != "flat_header"

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
        
        self.rebuild_visible_lines()
        
        # Clamp cursor index
        if not self.visible_lines:
            self.current_index = 0
        else:
            if self.current_index >= len(self.visible_lines):
                self.current_index = len(self.visible_lines) - 1
            # Adjust cursor if landing on a non-selectable line
            while self.current_index > 0 and not self.is_selectable(self.visible_lines[self.current_index]):
                self.current_index -= 1

    def rebuild_visible_lines(self):
        if self.group_by_folder:
            root_path = self.root_path.resolve()
            
            def make_node(name, full_path):
                return {
                    "name": name,
                    "children": {},
                    "item": None,
                    "is_target": False,
                    "full_path": full_path
                }

            tree_root = make_node(root_path.name or str(root_path), root_path)

            for idx, item in enumerate(self.filtered_items):
                item_path = Path(item["path"]).resolve()
                try:
                    rel_path = item_path.relative_to(root_path)
                    parts = rel_path.parts
                except ValueError:
                    parts = item_path.parts
                    
                curr_node = tree_root
                curr_path = root_path
                for part in parts:
                    curr_path = curr_path / part
                    if part not in curr_node["children"]:
                        curr_node["children"][part] = make_node(part, curr_path)
                    curr_node = curr_node["children"][part]
                curr_node["is_target"] = True
                curr_node["item"] = (item, idx)

            # Prune tree
            def prune(node):
                if node["is_target"]:
                    return True
                to_remove = [name for name, child in node["children"].items() if not prune(child)]
                for name in to_remove:
                    del node["children"][name]
                return len(node["children"]) > 0 or node["is_target"]

            prune(tree_root)

            # Flatten tree
            def flatten(node, prefix="", is_last=True, is_root=True):
                lines = []
                node_path_str = str(node["full_path"])
                is_expanded = self.folder_expanded.get(node_path_str, False)
                
                if is_root:
                    lines.append({
                        "type": "root",
                        "node": node
                    })
                else:
                    char = "└── " if is_last else "├── "
                    if node["is_target"]:
                        lines.append({
                            "type": "target",
                            "node": node,
                            "prefix": prefix + char
                        })
                    else:
                        lines.append({
                            "type": "folder",
                            "node": node,
                            "prefix": prefix + char
                        })
                    prefix += "    " if is_last else "│   "
                
                if is_root or is_expanded or node["is_target"]:
                    sorted_keys = sorted(node["children"].keys(), key=lambda x: x.lower())
                    for i, child_key in enumerate(sorted_keys):
                        child_is_last = (i == len(sorted_keys) - 1)
                        lines.extend(flatten(node["children"][child_key], prefix, child_is_last, False))
                return lines

            self.visible_lines = flatten(tree_root)
        else:
            # Group by type (flat list)
            if not self.filtered_items:
                self.visible_lines = []
                return
            
            groups = {}
            for idx, item in enumerate(self.filtered_items):
                g_key = item["type"]
                if g_key not in groups:
                    groups[g_key] = []
                groups[g_key].append((item, idx))
                
            sorted_groups = sorted(groups.keys(), key=lambda x: x.lower())
            
            lines = []
            for g_key in sorted_groups:
                lines.append({
                    "type": "flat_header",
                    "name": g_key
                })
                # Sort group items by size descending
                sorted_items = sorted(groups[g_key], key=lambda x: x[0]["size"], reverse=True)
                for item, idx in sorted_items:
                    lines.append({
                        "type": "flat_target",
                        "item": item,
                        "idx": idx
                    })
            self.visible_lines = lines

    def move_cursor_up(self):
        idx = self.current_index - 1
        while idx >= 0:
            if self.is_selectable(self.visible_lines[idx]):
                self.current_index = idx
                return
            idx -= 1

    def move_cursor_down(self):
        idx = self.current_index + 1
        while idx < len(self.visible_lines):
            if self.is_selectable(self.visible_lines[idx]):
                self.current_index = idx
                return
            idx += 1

    def get_lines(self):
        if not self.visible_lines:
            fragments = []
            fragments.append(("", "\n"))
            fragments.append(("class:help", "  (No items match the filter query)\n"))
            return fragments

        fragments = []
        self.highlighted_line_y = 0
        current_y = 0

        for idx, line in enumerate(self.visible_lines):
            is_hovered = idx == self.current_index
            if is_hovered:
                self.highlighted_line_y = current_y
                style_prefix = "class:item_highlighted"
                pointer_frag = ("class:pointer", " > ")
            else:
                style_prefix = ""
                pointer_frag = ("", "   ")

            if line["type"] in ("root", "folder"):
                node = line["node"]
                node_path_str = str(node["full_path"])
                is_expanded = self.folder_expanded.get(node_path_str, False)
                
                # Checkbox state
                cb_state = get_folder_cb_state(node, self.selected_paths)
                if cb_state == "checked":
                    cb_style = "class:checkbox_checked"
                    cb_char = "[x]"
                elif cb_state == "partial":
                    cb_style = "class:status"  # yellow
                    cb_char = "[-]"
                else:
                    cb_style = "class:checkbox_unchecked"
                    cb_char = "[ ]"
                
                # Expand icon
                exp_char = "▼ " if is_expanded else "▶ "
                name_str = node["name"] if line["type"] == "folder" else str(node["full_path"])
                
                node_targets = get_target_descendants(node)
                total_size = sum(item["size"] for item in node_targets)
                size_str = f" ({format_size(total_size)})" if total_size > 0 else ""
                
                prefix = line.get("prefix", "")
                fragments.extend([
                    pointer_frag,
                    ("", prefix),
                    (f"{style_prefix} {cb_style}", f"{cb_char} "),
                    (f"{style_prefix} class:pointer", exp_char),
                    (f"{style_prefix} class:group_header", f"📁 {name_str}"),
                    (f"{style_prefix} class:item_size", size_str),
                    (f"{style_prefix}", "\n")
                ])
                current_y += 1
            elif line["type"] == "target":
                node = line["node"]
                item, _ = node["item"]
                is_selected = str(item["long_path"]) in self.selected_paths
                
                cb_style = "class:checkbox_checked" if is_selected else "class:checkbox_unchecked"
                cb_char = "[x]" if is_selected else "[ ]"
                
                prefix = line["prefix"]
                fragments.extend([
                    pointer_frag,
                    ("", prefix),
                    (f"{style_prefix} {cb_style}", f"{cb_char} "),
                    (f"{style_prefix} class:item_type", f"{item['type']:<14}"),
                    (f"{style_prefix}", " | "),
                    (f"{style_prefix} class:item_size", f"{format_size(item['size']):<10}"),
                    (f"{style_prefix}", " | "),
                    (f"{style_prefix} class:item_path", f"{item['path'].name}\n")
                ])
                current_y += 1
            elif line["type"] == "flat_header":
                fragments.append(("class:group_header", f"\n--- {line['name']} ---\n"))
                current_y += 2
            elif line["type"] == "flat_target":
                item, _ = line["item"], line["idx"]
                is_selected = str(item["long_path"]) in self.selected_paths
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
        def get_header_text():
            if self.mode == "filter":
                mode_str = "FILTER MODE (Type to search | Press TAB/ESC to switch to Selection Mode)"
                help_str = "Up/Down: move cursor | Space: toggle | Backspace: delete | Ctrl+U: clear search"
            else:
                mode_str = "SELECTION MODE (Use J/K or arrows | Press TAB or '/' to search)"
                if self.group_by_folder:
                    help_str = "J/K: move | Space: toggle folder/target | Left/Right: collapse/expand | Enter: confirm"
                else:
                    help_str = "J/K/Arrows: move | Space: toggle target | Enter: confirm | Ctrl+C/Esc: exit"
            return [
                ("class:status", f" [{mode_str}] \n"),
                ("class:help", f" {help_str} ")
            ]
        header_window = Window(
            FormattedTextControl(get_header_text),
            height=2
        )

        # Search Bar
        def get_search_text():
            search_lbl = "🔍 Filter: "
            if self.mode == "filter":
                cursor_char = "_" if int(time.time() * 2) % 2 == 0 else " "
                return [
                    ("class:search_label", search_lbl),
                    ("class:search_query", self.filter_query),
                    ("class:search_query", cursor_char)
                ]
            else:
                return [
                    ("class:search_label", search_lbl),
                    ("class:search_query", self.filter_query),
                    ("class:help", " (Press TAB to edit)")
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

        # Mode toggles
        @kb.add("tab")
        def _(event):
            self.mode = "selection" if self.mode == "filter" else "filter"

        @kb.add("/")
        def _(event):
            if self.mode == "selection":
                self.mode = "filter"

        # Directional navigation (always works)
        @kb.add("up")
        def _(event):
            self.move_cursor_up()

        @kb.add("down")
        def _(event):
            self.move_cursor_down()

        # Vim-style navigation (selection mode only)
        @kb.add("k")
        def _(event):
            if self.mode == "selection":
                self.move_cursor_up()

        @kb.add("j")
        def _(event):
            if self.mode == "selection":
                self.move_cursor_down()

        # Expand / collapse (always works)
        @kb.add("left")
        def _(event):
            if self.group_by_folder and self.visible_lines:
                line = self.visible_lines[self.current_index]
                if line["type"] in ("root", "folder"):
                    node = line["node"]
                    self.folder_expanded[str(node["full_path"])] = False
                    self.rebuild_visible_lines()
                    self.current_index = min(self.current_index, len(self.visible_lines) - 1)

        @kb.add("right")
        def _(event):
            if self.group_by_folder and self.visible_lines:
                line = self.visible_lines[self.current_index]
                if line["type"] in ("root", "folder"):
                    node = line["node"]
                    self.folder_expanded[str(node["full_path"])] = True
                    self.rebuild_visible_lines()

        # Vim style expand/collapse (selection mode only)
        @kb.add("h")
        def _(event):
            if self.mode == "selection" and self.group_by_folder and self.visible_lines:
                line = self.visible_lines[self.current_index]
                if line["type"] in ("root", "folder"):
                    node = line["node"]
                    self.folder_expanded[str(node["full_path"])] = False
                    self.rebuild_visible_lines()
                    self.current_index = min(self.current_index, len(self.visible_lines) - 1)

        @kb.add("l")
        def _(event):
            if self.mode == "selection" and self.group_by_folder and self.visible_lines:
                line = self.visible_lines[self.current_index]
                if line["type"] in ("root", "folder"):
                    node = line["node"]
                    self.folder_expanded[str(node["full_path"])] = True
                    self.rebuild_visible_lines()

        # Toggle item/folder (always works)
        @kb.add("space")
        def _(event):
            if self.visible_lines:
                line = self.visible_lines[self.current_index]
                if line["type"] == "flat_target":
                    item = line["item"]
                    path_str = str(item["long_path"])
                    if path_str in self.selected_paths:
                        self.selected_paths.remove(path_str)
                    else:
                        self.selected_paths.add(path_str)
                    self.move_cursor_down()
                elif line["type"] == "target":
                    item, _ = line["node"]["item"]
                    path_str = str(item["long_path"])
                    if path_str in self.selected_paths:
                        self.selected_paths.remove(path_str)
                    else:
                        self.selected_paths.add(path_str)
                    self.move_cursor_down()
                elif line["type"] in ("root", "folder"):
                    node = line["node"]
                    descendants = get_target_descendants(node)
                    all_checked = all(str(item["long_path"]) in self.selected_paths for item in descendants)
                    if all_checked:
                        for item in descendants:
                            self.selected_paths.discard(str(item["long_path"]))
                    else:
                        for item in descendants:
                            self.selected_paths.add(str(item["long_path"]))

        # Typing controls (filter mode only)
        @kb.add("backspace")
        def _(event):
            if self.mode == "filter" and self.filter_query:
                self.filter_query = self.filter_query[:-1]
                self.update_filtered_list()

        @kb.add("c-u")
        def _(event):
            if self.mode == "filter":
                self.filter_query = ""
                self.update_filtered_list()

        # Confirmation & abort
        @kb.add("enter")
        def _(event):
            self.confirmed = True
            event.app.exit()

        @kb.add("escape")
        def _(event):
            if self.mode == "filter":
                self.mode = "selection"
            else:
                self.confirmed = False
                event.app.exit()

        @kb.add("c-c")
        def _(event):
            self.confirmed = False
            event.app.exit()

        # Catch-all for typing printable characters (filter mode only)
        @kb.add("<any>")
        def _(event):
            if self.mode == "filter":
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

def filter_checkbox_tui(items: list, group_by_folder: bool, root_path: Path) -> list:
    """
    Launches the custom filterable checkbox TUI.
    Returns the selected items list on confirm, or None on cancel/abort.
    """
    app = FilterableCheckboxApp(items, group_by_folder, root_path)
    return app.run()
