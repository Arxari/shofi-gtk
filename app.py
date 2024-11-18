#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib, Gdk
import os
from pathlib import Path
import json

class ShofiGTK(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='shofi-gtk')
        self.apps = []
        self.filtered_apps = []
        self.list_has_focus = False
        self.usage_data = {}
        self.load_usage_data()

    def load_usage_data(self):
        data_dir = Path(os.getenv('XDG_DATA_HOME', Path.home() / '.local/share')) / 'shofi-gtk'
        data_dir.mkdir(parents=True, exist_ok=True)
        self.usage_file = data_dir / 'usage.json'

        try:
            if self.usage_file.exists():
                with open(self.usage_file, 'r') as f:
                    self.usage_data = json.load(f)
        except Exception as e:
            print(f"Error loading usage data: {e}")
            self.usage_data = {}

    def get_app_id(self, app): # using desktop file names, if this is a bad idea someone let me know plz
        return app['app_info'].get_id() or app['exec']

    def get_app_usage(self, app):
        app_id = self.get_app_id(app)
        return self.usage_data.get(app_id, 0)

    def increment_app_usage(self, app):
        app_id = self.get_app_id(app)
        self.usage_data[app_id] = self.usage_data.get(app_id, 0) + 1
        self.save_usage_data()

    def save_usage_data(self):
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_data, f)
        except Exception as e:
            print(f"Error saving usage data: {e}")

    def do_activate(self):
        self.win = Gtk.ApplicationWindow(application=self)
        self.win.set_title("Shofi-GTK")
        self.win.set_default_size(600, 400)

        css_provider = Gtk.CssProvider()
        config_dir = Path(os.getenv('XDG_CONFIG_HOME', Path.home() / '.config')) / 'shofi-gtk'
        config_dir.mkdir(parents=True, exist_ok=True)
        css_file = config_dir / 'style.css'

        if not css_file.exists():
            css_file.write_text(DEFAULT_CSS)

        css_provider.load_from_path(str(css_file))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.win.set_child(main_box)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        search_box.set_css_classes(['search-box'])

        search_label = Gtk.Label(label="Search: ")
        search_label.set_css_classes(['search-label'])
        search_box.append(search_label)

        self.search_entry = Gtk.Entry()
        self.search_entry.connect('changed', self.on_search_changed)
        self.search_entry.set_hexpand(True)
        search_box.append(self.search_entry)

        main_box.append(search_box)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self.on_key_pressed)
        self.search_entry.add_controller(key_controller)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        main_box.append(scrolled)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.set_css_classes(['app-list'])
        self.list_box.connect('row-activated', self.on_row_activated)
        scrolled.set_child(self.list_box)

        list_key_controller = Gtk.EventControllerKey()
        list_key_controller.connect('key-pressed', self.on_list_key_pressed)
        self.list_box.add_controller(list_key_controller)

        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect('enter', self.on_list_focus_enter)
        focus_controller.connect('leave', self.on_list_focus_leave)
        self.list_box.add_controller(focus_controller)

        self.load_applications()
        sorted_apps = sorted(self.apps,
                           key=lambda x: (self.get_app_usage(x), x['name'].lower()),
                           reverse=True)
        self.display_apps(sorted_apps[:10])

        self.search_entry.grab_focus()

        self.win.present()

    def on_list_focus_enter(self, controller):
        self.list_has_focus = True

    def on_list_focus_leave(self, controller):
        self.list_has_focus = False

    def display_apps(self, apps_to_show):
        while True:
            child = self.list_box.get_first_child()
            if child is None:
                break
            self.list_box.remove(child)

        self.filtered_apps = apps_to_show
        for app in apps_to_show:
            self.list_box.append(self.create_app_row(app))

        if self.list_has_focus:
            first_row = self.list_box.get_row_at_index(0)
            if first_row:
                self.list_box.select_row(first_row)

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Down:
            first_row = self.list_box.get_row_at_index(0)
            if first_row:
                self.list_box.select_row(first_row)
                first_row.grab_focus()
                self.list_has_focus = True
            return True
        elif keyval == Gdk.KEY_Up:
            last_row = self.list_box.get_row_at_index(len(self.filtered_apps) - 1)
            if last_row:
                self.list_box.select_row(last_row)
                last_row.grab_focus()
                self.list_has_focus = True
            return True
        elif keyval == Gdk.KEY_Escape:
            self.win.close()
            return True
        return False

    def load_applications(self):
        self.apps = []
        xdg_data_home = os.getenv('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        desktop_paths = [
            Path(xdg_data_home) / 'applications',
            Path('/usr/share/applications'),
            Path('/usr/local/share/applications'),
            Path('/var/lib/flatpak/exports/share/applications'),
            Path(xdg_data_home) / 'flatpak/exports/share/applications'
        ]

        for path in desktop_paths:
            if path.exists():
                for desktop_file in path.glob('*.desktop'):
                    try:
                        app_info = Gio.DesktopAppInfo.new_from_filename(str(desktop_file))
                        if app_info and not app_info.get_nodisplay() and not app_info.get_is_hidden():
                            is_flatpak = 'flatpak' in str(desktop_file)
                            name = app_info.get_name()
                            if is_flatpak:
                                name = f"{name} (Flatpak)"

                            self.apps.append({
                                'name': name,
                                'icon': app_info.get_icon(),
                                'exec': app_info.get_executable(),
                                'desc': app_info.get_description() or '',
                                'app_info': app_info,
                                'is_flatpak': is_flatpak
                            })
                    except Exception as e:
                        print(f"Error loading {desktop_file}: {e}")

        self.apps.sort(key=lambda x: x['name'].lower())

    def create_app_row(self, app):
        list_box_row = Gtk.ListBoxRow()
        list_box_row.app_data = app

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_css_classes(['app-row'])

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        name_label = Gtk.Label(label=app['name'])
        name_label.set_css_classes(['app-name'])
        name_label.set_halign(Gtk.Align.START)
        text_box.append(name_label)

        if app['desc']:
            desc_label = Gtk.Label(label=app['desc'])
            desc_label.set_css_classes(['app-desc'])
            desc_label.set_halign(Gtk.Align.START)
            desc_label.set_wrap(True)
            text_box.append(desc_label)

        row.append(text_box)
        list_box_row.set_child(row)

        return list_box_row

    def move_selection(self, direction):
        current_row = self.list_box.get_selected_row()
        if current_row:
            current_index = current_row.get_index()
            if direction == 'up' and current_index > 0:
                new_row = self.list_box.get_row_at_index(current_index - 1)
                self.list_box.select_row(new_row)
                new_row.grab_focus()
            elif direction == 'down' and current_index < len(self.filtered_apps) - 1:
                new_row = self.list_box.get_row_at_index(current_index + 1)
                self.list_box.select_row(new_row)
                new_row.grab_focus()

    def on_list_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Up:
            current_row = self.list_box.get_selected_row()
            if current_row and current_row.get_index() == 0:
                self.search_entry.grab_focus()
                self.list_box.unselect_all()
                self.list_has_focus = False
            else:
                self.move_selection('up')
            return True
        elif keyval == Gdk.KEY_Down:
            self.move_selection('down')
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_Right):
            selected_row = self.list_box.get_selected_row()
            if selected_row:
                self.launch_app(selected_row.app_data)
            return True
        elif keyval == Gdk.KEY_Escape:
            self.win.close()
            return True
        return False

    def on_row_activated(self, list_box, row):
        if row and hasattr(row, 'app_data'):
            self.launch_app(row.app_data)

    def on_search_changed(self, entry):
        search_text = entry.get_text().lower()
        if search_text:
            filtered = [app for app in self.apps
                       if search_text in app['name'].lower() or
                          search_text in (app['desc'] or '').lower()]
            filtered.sort(key=lambda x: (
                not x['name'].lower().startswith(search_text),
                not search_text in x['name'].lower(),
                -self.get_app_usage(x),
                x['name'].lower()
            ))
        else:
            filtered = sorted(self.apps,
                            key=lambda x: (self.get_app_usage(x), x['name'].lower()),
                            reverse=True)[:10]

        self.display_apps(filtered)

    def launch_app(self, app):
        try:
            app['app_info'].launch()
            self.increment_app_usage(app)
            self.win.close()
        except Exception as e:
            print(f"Error launching {app['name']}: {e}")

DEFAULT_CSS = """
window {
    background-color: #1a1b26;
    color: #a9b1d6;
}

/* Hide scrollbar */
scrolledwindow undershoot.top,
scrolledwindow undershoot.bottom,
scrolledwindow overshoot.top,
scrolledwindow overshoot.bottom,
scrolledwindow scrollbar {
    opacity: 0;
    -gtk-icon-size: 0;
    min-width: 0;
    min-height: 0;
}

.search-box {
    margin: 8px 12px;
    padding: 0;
}

.search-label {
    font-family: monospace;
    font-size: 14px;
    color: #7aa2f7;
    margin-right: 8px;
}

entry {
    font-family: monospace;
    font-size: 14px;
    background: transparent;
    color: #a9b1d6;
    border: none;
    box-shadow: none;
    padding: 0;
    margin: 0;
    min-height: 0;
    outline: none;
    -gtk-outline-radius: 0;
}

.app-list {
    margin: 0 8px;
    background: transparent;
}

.app-row {
    padding: 8px 12px;
    background-color: transparent;
    color: #a9b1d6;
}

.app-name {
    font-family: monospace;
    font-size: 13px;
    color: #7aa2f7;
}

.app-desc {
    font-family: monospace;
    font-size: 12px;
    color: #565f89;
}

row {
    padding-left: 12px;
    transition: none;
}

.app-list {
    counter-reset: row-number;
}

row {
    counter-increment: row-number;
}

row:not(:selected)::before {
    content: " " counter(row-number) ")";
    font-family: monospace;
    color: #565f89;
    margin-right: 8px;
}

row:selected {
    background: transparent;
}

row:selected::before {
    content: ">" counter(row-number) ")";
    font-family: monospace;
    color: #7aa2f7;
    margin-right: 8px;
}

row:selected .app-name {
    color: #7aa2f7;
}

row:selected .app-desc {
    color: #a9b1d6;
}

/* Removes default GTK selection styling */
row:selected:focus {
    outline: none;
    box-shadow: none;
}
"""

if __name__ == '__main__':
    app = ShofiGTK()
    app.run()
