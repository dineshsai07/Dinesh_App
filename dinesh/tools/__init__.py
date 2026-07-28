"""Tool registry — all Dinesh capabilities + core subset for small models."""

from tools import browser_tools as browser
from tools import code_tools as code
from tools import file_tools as files
from tools import gui_tools as gui
from tools import mac_tools as mac
from tools import shell_tools as shell
from tools import vision_tools as vision
from tools import web_tools as web

TOOL_MAP = {
    "see_screen": vision.see_screen,
    "analyze_image": vision.analyze_image,
    "find_element_on_screen": vision.find_element_on_screen,
    "capture_screen": gui.capture_screen,
    "get_screen_size": gui.get_screen_size,
    "get_mouse_position": gui.get_mouse_position,
    "move_mouse": gui.move_mouse,
    "click_at": gui.click_at,
    "double_click_at": gui.double_click_at,
    "right_click_at": gui.right_click_at,
    "scroll": gui.scroll,
    "type_text": gui.type_text,
    "press_key": gui.press_key,
    "hotkey": gui.hotkey,
    "drag": gui.drag,
    "list_windows": gui.list_windows,
    "focus_app": gui.focus_app,
    "minimize_front_window": gui.minimize_front_window,
    "close_front_window": gui.close_front_window,
    "show_notification": gui.show_notification,
    "browser_open_url": browser.browser_open_url,
    "browser_click": browser.browser_click,
    "browser_type": browser.browser_type,
    "browser_read_page": browser.browser_read_page,
    "browser_screenshot": browser.browser_screenshot,
    "browser_go_back": browser.browser_go_back,
    "browser_search": browser.browser_search,
    "browser_close": browser.browser_close,
    "open_app": mac.open_app,
    "open_path": mac.open_path,
    "open_url": mac.open_url,
    "set_reminder": mac.set_reminder,
    "set_volume": mac.set_volume,
    "get_clipboard": mac.get_clipboard,
    "set_clipboard": mac.set_clipboard,
    "run_applescript": mac.run_applescript,
    "send_email": mac.send_email,
    "create_calendar_event": mac.create_calendar_event,
    "take_screenshot": mac.take_screenshot,
    "create_file": files.create_file,
    "read_file": files.read_file,
    "write_file": files.write_file,
    "append_file": files.append_file,
    "create_folder": files.create_folder,
    "list_files": files.list_files,
    "move_file": files.move_file,
    "copy_file": files.copy_file,
    "delete_path": files.delete_path,
    "web_search": web.web_search,
    "fetch_webpage": web.fetch_webpage,
    "get_storage": shell.get_storage,
    "get_battery": shell.get_battery,
    "get_time_and_date": shell.get_time_and_date,
    "get_system_info": shell.get_system_info,
    "get_cpu_usage": shell.get_cpu_usage,
    "get_resource_summary": shell.get_resource_summary,
    "run_command": shell.run_command,
    "list_processes": shell.list_processes,
    "run_python": code.run_python,
}

TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "run_python", "description": "PREFERRED for file/folder/HTML tasks. Run short Python. Preloaded: Path, HOME, DESKTOP. Example: DESKTOP.joinpath('AboutMe').mkdir(exist_ok=True); (DESKTOP/'AboutMe'/'index.html').write_text('<h1>Hi</h1>')", "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {"name": "see_screen", "description": "Capture and describe the screen with vision.", "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "find_element_on_screen", "description": "Find UI element coords by description.", "parameters": {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]}}},
    {"type": "function", "function": {"name": "click_at", "description": "Click at x,y.", "parameters": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "string"}, "clicks": {"type": "integer"}}, "required": ["x", "y"]}}},
    {"type": "function", "function": {"name": "type_text", "description": "Type text at focus.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "press_key", "description": "Press a key.", "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}}},
    {"type": "function", "function": {"name": "hotkey", "description": "Key combo.", "parameters": {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}}}, "required": ["keys"]}}},
    {"type": "function", "function": {"name": "scroll", "description": "Scroll. Positive=up.", "parameters": {"type": "object", "properties": {"amount": {"type": "integer"}}, "required": ["amount"]}}},
    {"type": "function", "function": {"name": "list_windows", "description": "List visible apps.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "focus_app", "description": "Focus app.", "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]}}},
    {"type": "function", "function": {"name": "open_app", "description": "Open a macOS app. Misspelled names are corrected automatically.", "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]}}},
    {"type": "function", "function": {"name": "open_path", "description": "Open a file or folder in Finder, e.g. ~/Downloads.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "open_url", "description": "Open URL in default browser.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "browser_open_url", "description": "Open URL in Playwright.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "browser_type", "description": "Type in browser field.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "text": {"type": "string"}, "submit": {"type": "boolean"}}, "required": ["selector", "text"]}}},
    {"type": "function", "function": {"name": "browser_read_page", "description": "Read browser page.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "create_folder", "description": "Create folder. Path like ~/Desktop/MyFolder.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "create_file", "description": "Create file with content.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Overwrite a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "list_files", "description": "List folder.", "parameters": {"type": "object", "properties": {"folder": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "run_command", "description": "Run shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "web_search", "description": "Web search. Use for news, facts, current events.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "fetch_webpage", "description": "Download and extract text from a URL. Use when user wants content from a specific site.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "get_time_and_date", "description": "Current time.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_battery", "description": "Battery.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_storage", "description": "Disk space only.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_cpu_usage", "description": "Current CPU usage on this Mac.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_resource_summary", "description": "CPU + RAM + storage together. Use when user asks about system/PC utilization.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_system_info", "description": "Uptime and free RAM.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "set_volume", "description": "Volume 0-100.", "parameters": {"type": "object", "properties": {"level": {"type": "integer"}}, "required": ["level"]}}},
    {"type": "function", "function": {"name": "take_screenshot", "description": "Screenshot to Desktop.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "set_reminder", "description": "Create reminder.", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "minutes_from_now": {"type": "integer"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "run_applescript", "description": "Run AppleScript.", "parameters": {"type": "object", "properties": {"script": {"type": "string"}}, "required": ["script"]}}},
]

CORE_TOOL_NAMES = {
    "run_python", "see_screen", "open_app", "open_path", "open_url",
    "create_folder", "create_file", "write_file", "read_file", "list_files",
    "run_command", "web_search", "fetch_webpage",
    "get_time_and_date", "get_cpu_usage", "get_resource_summary", "get_storage",
    "take_screenshot", "click_at", "type_text", "list_windows", "focus_app",
}

CORE_TOOLS_SCHEMA = [t for t in TOOLS_SCHEMA if t["function"]["name"] in CORE_TOOL_NAMES]


def active_tools_schema(weak_model: bool = False):
    return CORE_TOOLS_SCHEMA if weak_model else TOOLS_SCHEMA
