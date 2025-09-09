# Nightfall MUD Client - Complete Program Structure & Call Flow

## Overview
This document maps the complete function call hierarchy of the Nightfall MUD Client, showing which functions can call which other functions throughout the codebase.

## Entry Point & Main Flow

```
main.py::main()
├── install.main() [direct import and call]
│   ├── check_tkinter()
│   └── install(package) [for each missing package]
├── tk.Tk() [creates root window]
├── MainWindow(root) [initializes application]
│   └── [See MainWindow section below]
└── root.mainloop() [starts event loop]
```

## Module-by-Module Call Relationships

### 1. main.py
```
main()
├── os.chdir()
├── os.path.dirname()
├── os.path.abspath()
├── install.main() [imported directly]
├── tk.Tk()
├── MainWindow(root)
├── root.protocol("WM_DELETE_WINDOW", ...)
├── root.destroy()
└── root.mainloop()
```

### 2. gui/mainwindow.py::MainWindow
```
__init__(root)
├── load_config() [from config.settings]
├── initialize_window()
│   └── [tkinter window setup methods]
├── load_trigger_commands()
│   ├── open() [file I/O]
│   └── json.load()
├── MUDConnectionWrapper() [from network.async_connection]
├── ThemeManager() [from gui.themes]
├── setup_ui()
│   ├── ttk.PanedWindow()
│   ├── MapViewer(parent, pane, root, theme_manager)
│   ├── setup_console_ui()
│   │   └── [tkinter widget creation]
│   └── setup_toolbar()
│       └── [tkinter widget creation]
├── AutoWalker(map_viewer) [from core.positionfinder]
├── setup_bindings()
│   └── [tkinter event bindings]
└── apply_theme()
    └── theme_manager.get_theme()

handle_message(message)
├── ANSI_Color_Text(message)
│   └── get_ansi_color(code)
├── auto_walker.analyze_response(message)
│   └── [See AutoWalker section]
├── append_to_buffer(text, color_tag)
│   └── schedule_update()
│       └── update_text_area()
└── apply_description_highlighting(highlight_info)

handle_return(event)
├── connection.send(command)
├── append_to_buffer()
├── show_prompt()
└── auto_walker.analyze_response(command, is_look_command=True)

on_login_success()
├── connection.save_credentials()
├── mapviewer.initialize_ui()
└── auto_walker.toggle_active()

Other methods:
├── copy_text() → clipboard operations
├── paste_text() → clipboard operations
├── cycle_command_history_up/down() → history management
└── change_theme() → theme_manager.set_theme() → apply_theme()
```

### 3. map/map.py::MapViewer
```
__init__(parent, pane, root, theme_manager)
├── Camera(canvas) [from map.camera]
├── RoomCustomization() [from map.room_customization]
├── load_config() [from config.settings]
├── get_database() [from core.fast_database]
└── fetch_zone_dict() [database calls]
    ├── _db.get_all_zones()
    └── _db.get_zone_name(zone_id)

display_zone(zone_id, auto_fit)
├── _db.get_rooms_in_zone(zone_id, z_level)
├── _db.get_exits_with_zone_info(room_ids)
├── draw_map(rooms, exits_info)
│   ├── canvas operations
│   ├── room_customization.get_room_customization()
│   └── ToolTip(canvas) [from gui.tooltip]
├── camera.restore_zone_state(zone_id)
└── camera.fit_to_content()

draw_map(rooms, exits_info)
├── canvas.delete("all")
├── draw_exits(rooms, exits)
├── draw_room_with_shadow() [for each room]
│   ├── room_customization.get_room_customization(room_id)
│   ├── canvas.create_rectangle() [room shadow]
│   ├── canvas.create_rectangle() [room body]
│   └── canvas.create_text() [note indicator if exists]
├── place_zone_change_note() [for zone transitions]
└── calculate_direction(from_pos, to_pos)

get_room_tooltip_text(room_id)
├── _db.get_room_name(room_id)
└── room_customization.get_room_customization(room_id)

show_room_name(event, room_id, event_x, event_y)
├── get_room_tooltip_text(room_id)
├── ToolTip(self.this) [if not exists]
└── tooltip.show_tip(room_name, event_x, event_y)

highlight_room(room_id)
├── _db.get_room_position(room_id)
├── center_on_room(room_id)
│   └── camera.center_on_point(x, y)
└── canvas operations for highlighting

pathfind_to_room(target_room_id)
├── find_path(current_room_id, target_room_id)
│   └── _db.get_exits_with_zone_info()
├── _db.get_room_name(room_id)
└── connection.send(command) [for each path step]

show_room_search_dialog()
├── tk.Toplevel()
├── _db.get_rooms_in_zone()
├── _db.get_zone_name()
└── display_zone() → highlight_room()

show_item_search_dialog()
├── tk.Toplevel()
├── json.load() [room_items.json]
├── _db.get_room_zone()
├── _db.get_zone_name()
└── display_zone() → highlight_room()

on_right_click(event)
├── tk.Menu()
├── RoomCustomizationDialog() [from map.room_customization]
└── room_customization operations
```

### 4. core/fast_database.py
```
FastDatabase class:
__init__()
└── load_database()
    ├── os.path.exists()
    ├── open() → json.load()
    └── logging operations

get_room(room_id)
└── self.data["rooms"].get(str(room_id))

get_room_name(room_id)
└── get_room(room_id)

get_room_description(room_id)
└── get_room(room_id)

get_room_position(room_id)
└── get_room(room_id)

get_room_zone(room_id)
└── get_room(room_id)

get_room_exits(room_id)
└── get_room(room_id)

get_connected_rooms(room_id)
└── get_room(room_id)

get_zone(zone_id)
└── self.data["zones"].get(str(zone_id))

get_zone_name(zone_id)
└── get_zone(zone_id)

get_all_zones()
└── iterate self.data["zones"]

get_rooms_in_zone(zone_id, z_level)
├── self.data["zone_rooms"].get(str(zone_id))
└── get_room(rid) [for each room]

get_exits_from_room(room_id)
└── self.data["exits"].get(str(room_id))

get_exits_with_zone_info(from_room_ids)
├── get_exits_from_room(from_id)
└── get_room(to_id)

find_room_by_description(search_text, threshold)
├── Levenshtein.ratio()
└── self.data["descriptions_index"]

find_rooms_by_name(search_name)
└── self.data["names_index"]

get_all_room_descriptions()
└── self.data["descriptions_index"]

get_connected_room_descriptions(current_room_id)
├── get_connected_rooms(current_room_id)
└── get_room(rid) [for each connected room]

Global function:
get_database()
└── FastDatabase() [singleton pattern]
```

### 5. core/positionfinder.py::AutoWalker
```
__init__(map_viewer)
├── stores reference to map_viewer
└── get_database() [from core.fast_database]

analyze_response(response, is_look_command)
└── threading.Thread(target=_process_response)
    └── _process_response(response, is_look_command)

_process_response(response, is_look_command)
├── _extract_exit_info(response)
├── _db.get_all_room_descriptions() or _db.get_connected_room_descriptions()
├── _find_matching_room_with_exits() or _find_matching_room()
│   ├── _clean_text_for_matching()
│   └── Levenshtein.ratio()
├── _perform_full_text_comparison()
│   └── Levenshtein.ratio()
├── _calculate_highlighting()
│   ├── _clean_text_for_matching()
│   ├── _create_highlight_map()
│   └── _map_to_original_positions()
├── _extract_items_and_npcs(response)
├── _save_room_entities(room_id, entities)
│   ├── json.load()
│   └── json.dump()
├── _db.get_room_zone(room_id)
├── map_viewer.display_zone(zone_id)
├── map_viewer.highlight_room(room_id)
└── map_viewer.root.after() [GUI thread callback]

set_current_room(room_id)
└── stores current_room_id

toggle_active()
└── toggles self.active flag
```

### 6. network/async_connection.py
```
MUDConnectionWrapper class:
__init__(callbacks)
└── stores callback functions

connect()
├── threading.Thread(target=_run_async_loop)
│   └── asyncio.run(AsyncMUDConnection.connect())
└── AsyncMUDConnection.connect()
    ├── load_config() [from config.settings]
    ├── asyncio.open_connection()
    ├── asyncio.create_task(_receive_loop)
    └── asyncio.create_task(_timeout_checker)

send(data)
└── asyncio.run_coroutine_threadsafe(async_conn.send())

send_raw(raw_bytes)
└── asyncio.run_coroutine_threadsafe(async_conn.send_raw())

save_credentials(username, password)
├── load_config() [from config.settings]
└── save_config() [from config.settings]

AsyncMUDConnection class:
_receive_loop()
├── reader.read()
├── process_telnet(data, writer)
└── protocol.process_data(data)
    ├── handle_login()
    └── _check_for_complete_messages()

MUDStreamProtocol class:
process_data(data)
├── handle_login()
├── _check_for_complete_messages()
└── _flush_buffer()
```

### 7. gui/themes.py::ThemeManager
```
__init__()
├── define theme dictionaries
└── load_theme_preference()
    ├── os.path.exists()
    └── json.load()

set_theme(theme_name)
└── save_theme_preference()
    ├── os.makedirs()
    └── json.dump()

get_theme()
└── returns current theme dict

apply_theme_to_widget(widget, widget_type)
└── widget.configure() with theme colors
```

### 8. config/settings.py
```
load_config()
├── ConfigParser()
├── config.read()
└── returns config dict

save_config(settings)
├── ConfigParser()
├── config.read()
├── config.set() [for each setting]
├── os.makedirs()
└── config.write()
```

### 9. map/camera.py::Camera
```
__init__(canvas, initial_position, initial_zoom)
├── load_states_from_file()
│   ├── os.path.exists()
│   └── json.load()
└── canvas.bind() [mouse events]

start_pan(event)
└── stores pan start position

on_pan(event)
├── canvas.scan_dragto()
└── update_scroll_region()

on_zoom(event)
├── canvas.scale()
├── apply_current_zoom()
└── update_scroll_region()

save_zone_state(zone_id)
└── stores current view state

restore_zone_state(zone_id)
├── retrieves saved state
└── apply_pending_view()
    ├── canvas.configure()
    └── canvas operations

center_on_point(x, y)
├── canvas.bbox()
├── canvas.xview_moveto()
└── canvas.yview_moveto()

fit_to_content(padding)
├── canvas.bbox("all")
├── calculate zoom
└── apply zoom and center

save_states_to_file()
├── os.makedirs()
└── json.dump()
```

### 10. map/room_customization.py
```
RoomCustomization class:
__init__()
└── load_customizations()
    ├── os.path.exists()
    └── json.load()

save_customizations()
├── os.makedirs()
└── json.dump()

get_room_customization(room_id)
└── returns customization dict

set_room_customization(room_id, customization)
└── save_customizations()

clear_room_customization(room_id)
└── save_customizations()

RoomCustomizationDialog class:
__init__(parent, room_id, room_name, customization_manager)
├── tk.Toplevel()
└── create GUI elements

choose_color()
└── colorchooser.askcolor()

save()
├── customization_manager.set_room_customization()
└── parent.refresh_display()

show()
└── dialog.grab_set() → wait_window()
```

### 11. gui/tooltip.py::ToolTip
```
__init__(widget)
└── stores widget reference

show_tip(tip_text, event_x, event_y)
├── tk.Toplevel()
├── tk.Frame()
└── tk.Label()

hide_tip()
└── tip_window.destroy()
```

### 12. install.py
```
main()
├── check_tkinter()
│   └── __import__("tkinter")
└── install(package) [for each package]
    └── subprocess.check_call([sys.executable, "-m", "pip", "install", package])
```

## Cross-Module Call Patterns

### Database Access Pattern
```
Any Module
└── get_database() [from core.fast_database]
    └── _db.get_*() methods
        └── self.data[key] [in-memory JSON data]
```

### Network Communication Pattern
```
MainWindow.handle_return() or other trigger
└── connection.send(command)
    └── AsyncMUDConnection.send()
        └── writer.write() [to socket]

Network receives data:
AsyncMUDConnection._receive_loop()
└── protocol.process_data()
    └── on_message callback
        └── MainWindow.handle_message()
            └── AutoWalker.analyze_response()
                └── MapViewer updates
```

### Theme Application Pattern
```
MainWindow.change_theme()
└── ThemeManager.set_theme()
    └── MainWindow.apply_theme()
        └── ThemeManager.get_theme()
            └── Apply to all widgets
```

### Position Finding Pattern
```
MainWindow.handle_message(response)
└── AutoWalker.analyze_response(response)
    └── Threading.Thread(_process_response)
        ├── Database lookups via _db
        ├── Levenshtein matching
        └── MapViewer.highlight_room()
```

## Event-Driven Callbacks

### Network Events
- `on_message` → MainWindow.handle_message()
- `on_login_success` → MainWindow.on_login_success()
- `on_login_prompt` → MainWindow.on_login_prompt()

### GUI Events
- Mouse events → Camera pan/zoom operations
- Keyboard events → Terminal input handling
- Right-click → Context menus and customization dialogs

### Timer Events
- `root.after()` → Scheduled GUI updates
- Async timeout checker → Connection management

## File I/O Operations

### JSON Files Read/Written
- `data/nightfall_world.json` - Main database
- `data/room_items.json` - Item locations
- `data/room_customizations.json` - User customizations
- `data/camera_states.json` - Camera positions
- `data/theme_preference.json` - Selected theme
- `trigger_commands.json` - Auto-commands

### Config Files
- `settings.ini` - Application settings

## External Dependencies Called

### Python Standard Library
- `tkinter` - All GUI operations
- `asyncio` - Async networking
- `socket` - Network connections
- `threading` - Background processing
- `json` - Data persistence
- `configparser` - Settings management
- `os`, `sys` - System operations
- `subprocess` - Install script

### Third-Party Libraries
- `Levenshtein` - String similarity matching

## Architecture Improvements Made

### Removed Redundancies
1. **Eliminated legacy sync connection** - Removed `network/connection.py`
2. **Removed unused integrated terminal** - Deleted `gui/integrated_terminal.py`
3. **Eliminated database proxy layer** - Removed `core/database.py`, direct access to `fast_database`
4. **Fixed duplicate customization calls** - Created `get_room_tooltip_text()` helper method
5. **Improved install process** - Direct import instead of `os.system()`

### Benefits of Refactoring
- **Cleaner architecture** - No unnecessary indirection layers
- **Better performance** - Direct database access without proxy overhead
- **Reduced complexity** - Fewer files and simpler call chains
- **Improved maintainability** - Clear single responsibility for each module
- **No duplicate code** - Consolidated repeated logic into helper methods