#!/usr/bin/env python3
"""
mdread - A minimal markdown reader for Linux
In the spirit of zathura/sxiv: keyboard-driven, no editing, just reading.

Usage:
    mdread file.md

Keybindings:
    j / Down        Scroll down
    k / Up          Scroll up
    d               Half page down
    u               Half page up
    g / Home        Top of document
    G / End         Bottom of document
    {               Previous heading
    }               Next heading
    f / F11         Toggle fullscreen
    + / =           Zoom in
    -               Zoom out
    0               Reset zoom
    r               Reload file
    /               Search (incremental)
    Enter / Escape  Close search bar
    n               Next search match
    p               Previous search match
    Escape          Clear search highlights (when not searching)
    o               Link hints (type number + Enter to open)
    q               Quit
"""

import sys
import os
import signal
import argparse
import subprocess
import shutil
from pathlib import Path
from importlib import resources

try:
    import gi

    gi.require_version("Gtk", "3.0")
    try:
        gi.require_version("WebKit2", "4.1")
    except ValueError:
        gi.require_version("WebKit2", "4.0")
    from gi.repository import Gtk, Gdk, WebKit2, GLib
except ImportError as e:
    print(f"Error: GTK3 or WebKit2 dependencies not found.\n{e}")
    print("\nPlease ensure GObject Introspection and WebKit2GTK are installed.")
    print("Example (Debian/Ubuntu): sudo apt install python3-gi gir1.2-webkit2-4.1")
    print("Example (Fedora):        sudo dnf install python3-gobject webkit2gtk4.1")
    sys.exit(1)

try:
    import markdown
except ImportError:
    print("Error: Python 'markdown' package not found.")
    print("\nInstall it via:")
    print("  pip install markdown")
    print("  uv add markdown (if using a virtualenv)")
    sys.exit(1)

try:
    import pygments  # noqa: F401

    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False


# ── HTML/CSS injected into the rendered page ──────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Literata:ital,wght@0,300;0,400;0,600;1,300;1,400&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg:        #101010;
    --surface:   #161616;
    --border:    #343434;
    --text:      #A0A0A0;
    --muted:     #65737E;
    --accent:    #FFCFA8;
    --accent2:   #99FFE4;
    --code-bg:   #161616;
    --link:      #FFCFA8;
    --hr:        #232323;
    --quote-bar: #FFCFA8;

    --orange: #FFC799;
    --cyan: #99FFE4;
        
}



* { box-sizing: border-box; margin: 0; padding: 0; }

html {
    background: var(--bg);
    color: var(--text);
    font-family: 'Literata', Georgia, serif;
    font-size: 18px;
    line-height: 1.75;
    scroll-behavior: smooth;
}

body {
    max-width: 960px;
    margin: 0 auto;
    padding: 3rem 2rem 6rem;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Literata', Georgia, serif;
    font-weight: 600;
    color: var(--accent);
    line-height: 1.3;
    margin: 2.2rem 0 0.8rem;
}
h1 { font-size: 2rem;   border-bottom: 1px solid var(--border); padding-bottom: .5rem; }
h2 { font-size: 1.5rem; border-bottom: 1px solid var(--border); padding-bottom: .3rem; }
h3 { font-size: 1.2rem; color: var(--accent2); }
h4 { font-size: 1.05rem; color: var(--accent2); }
h5, h6 { font-size: 1rem; color: var(--muted); }

p { margin: 1rem 0; }

a { color: var(--link); text-decoration: none; border-bottom: 1px solid transparent; transition: border-color .15s; }
a:hover { border-color: var(--link); }

strong { color: #FEFEFE; font-weight: 600; }
em     { color: #d0d0d0; font-style: italic; }

code {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: .82em;
    background: var(--code-bg);
    color: var(--orange);
    padding: .15em .4em;
    border-radius: 3px;
    border: 1px solid var(--border);
}

pre {
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 4px;
    padding: 1.1rem 1.3rem;
    overflow-x: auto;
    margin: 1.4rem 0;
    line-height: 1.55;
}
pre code {
    background: none;
    border: none;
    padding: 0;
    font-size: .84em;
    color: white;
}

.highlight { background: var(--code-bg) !important; border-radius: 4px; color: var(--text); }
.highlight .k, .highlight .kn, .highlight .kd, .highlight .kp, .highlight .kr, .highlight .ow, .highlight .ow { color: var(--muted); }
.highlight .nf, .highlight .nc, .highlight .fm, .highlight .nb { color: var(--orange); }
.highlight .kt, .highlight .nc, .highlight .no { color: var(--orange); }
.highlight .s, .highlight .s1, .highlight .s2, .highlight .sb, .highlight .sc, .highlight .sd { color: var(--cyan); }
.highlight .c, .highlight .c1, .highlight .cm, .highlight .ch { color: var(--muted); font-style: italic; }
.highlight .m, .highlight .mi, .highlight .mf { color: var(--cyan); }
.highlight .nv, .highlight .no, .highlight .nn, .highlight .n { color: white; }                   /* Names/Identifiers: FG */
.highlight .p { color: var(--text); }                                                                 /* Punctuation (braces etc): Muted */

blockquote {
    border-left: 3px solid var(--quote-bar);
    margin: 1.4rem 0;
    padding: .6rem 1.2rem;
    background: var(--surface);
    border-radius: 0 4px 4px 0;
    color: var(--muted);
    font-style: italic;
}
blockquote p { margin: .3rem 0; }

ul, ol { padding-left: 1.6rem; margin: .8rem 0; }
li { margin: .3rem 0; }
li > ul, li > ol { margin: .2rem 0; }
ul li::marker { color: var(--accent); }
ol li::marker { color: var(--muted); font-size: .9em; }

table { width: 100%; border-collapse: collapse; margin: 1.4rem 0; font-size: .93em; }
th { background: var(--surface); color: var(--accent); font-weight: 600; text-align: left; padding: .6rem .9rem; border-bottom: 2px solid var(--accent); }
td { padding: .5rem .9rem; border-bottom: 1px solid var(--border); }
tr:hover td { background: var(--surface); }

hr { border: none; border-top: 1px solid var(--hr); margin: 2.5rem 0; }

img { max-width: 100%; height: auto; border-radius: 4px; margin: 1rem 0; display: block; }

input[type="checkbox"] { accent-color: var(--accent); margin-right: .4em; }

::-webkit-scrollbar       { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #505050; }

::selection { background: rgba(255, 207, 168, .15); }

.link-hint {
    position: absolute;
    background: var(--accent);
    color: var(--bg);
    font-size: 11px;
    font-weight: 700;
    padding: 0 4px;
    border-radius: 3px;
    pointer-events: none;
    z-index: 9999;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.4;
    box-shadow: 0 1px 3px rgba(0,0,0,.4);
}
"""

# ── GTK CSS for the native search bar widget ──────────────────────────

GTK_CSS = b"""
.search-bar {
    background-color: #161616;
    border-top: 1px solid #343434;
    padding: 2px 0;
    min-height: 28px;
}
.search-prompt {
    color: #FFCFA8;
    font-family: monospace;
    font-weight: bold;
    font-size: 14px;
}
.search-entry {
    background: transparent;
    color: #A0A0A0;
    border: none;
    box-shadow: none;
    font-family: monospace;
    font-size: 14px;
    caret-color: #FFCFA8;
}
.search-entry:focus {
    box-shadow: none;
    outline: none;
}
.search-count {
    color: #65737E;
    font-family: monospace;
    font-size: 12px;
}
.search-no-match {
    color: #FF8080;
    font-family: monospace;
    font-size: 12px;
}
"""


def md_to_html(filepath: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        text = f"**Error reading file:** {e}"

    extensions = [
        "fenced_code",
        "tables",
        "toc",
        "nl2br",
        "footnotes",
        "attr_list",
        "def_list",
        "abbr",
        "meta",
        "sane_lists",
        "smarty",
    ]
    extension_configs = {}

    if HAS_PYGMENTS:
        extensions.append("codehilite")
        extension_configs["codehilite"] = {
            "css_class": "highlight",
            "guess_lang": False,
            "noclasses": False,
            "pygments_style": "default",
        }

    md = markdown.Markdown(
        extensions=extensions,
        extension_configs=extension_configs,
        output_format="html5",
    )
    body = md.convert(text)
    file_dir = os.path.dirname(os.path.abspath(filepath))

    title = os.path.basename(filepath)
    if hasattr(md, "Meta") and "title" in md.Meta:
        title = md.Meta["title"][0]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<base href="file://{file_dir}/">
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


class MarkdownReader(Gtk.Window):
    SCROLL_STEP = 80
    ZOOM_STEP = 0.1

    MODE_NORMAL = "normal"
    MODE_SEARCH = "search"
    MODE_LINK_HINT = "link_hint"

    def __init__(self, filepath: str):
        super().__init__(title=os.path.basename(filepath))
        self.filepath = os.path.abspath(filepath)
        self.fullscreen_on = False
        self._win_height = 700
        self._mode = self.MODE_NORMAL
        self._last_search = ""

        self.set_default_size(900, 700)
        self._apply_gtk_css()

        # ── WebView settings ──────────────────────────
        settings = WebKit2.Settings()
        # JS must be ON — we use it for scrollBy/scrollTo and link hints
        settings.set_enable_javascript(True)
        settings.set_allow_modal_dialogs(False)
        settings.set_enable_media(False)
        settings.set_enable_webaudio(False)
        settings.set_default_font_family("serif")
        settings.set_default_font_size(18)
        settings.set_enable_write_console_messages_to_stdout(False)

        self.webview = WebKit2.WebView()
        self.webview.set_settings(settings)

        # Intercept all navigation
        self.webview.connect("decide-policy", self._on_policy)

        # ── Find controller (native WebKit search) ────
        self._find_controller = self.webview.get_find_controller()
        self._find_controller.connect("found-text", self._on_found_text)
        self._find_controller.connect("failed-to-find-text", self._on_not_found)

        # ── KEY EVENTS: attach to the WebView widget ──
        # WebKit's internal input widget captures keys before the GTK window
        # handler fires. Connecting directly to the WebView (with the event
        # mask set) intercepts them first.
        self.webview.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        self.webview.connect("key-press-event", self._on_key)

        # Window-level fallback (active before first focus / click)
        self.connect("key-press-event", self._on_key)
        self.connect("size-allocate", self._on_resize)
        self.connect("destroy", Gtk.main_quit)

        # ── Layout ────────────────────────────────────
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.webview)
        scroll.connect("edge-reached", self._on_scroll_edge)
        vbox.pack_start(scroll, True, True, 0)

        # ── Search bar (bottom, zathura-style) ────────
        self._search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._search_box.get_style_context().add_class("search-bar")

        prompt = Gtk.Label(label="/")
        prompt.get_style_context().add_class("search-prompt")
        self._search_box.pack_start(prompt, False, False, 8)

        self._search_entry = Gtk.Entry()
        self._search_entry.set_has_frame(False)
        self._search_entry.get_style_context().add_class("search-entry")
        self._search_box.pack_start(self._search_entry, True, True, 0)

        self._match_label = Gtk.Label()
        self._match_label.get_style_context().add_class("search-count")
        self._search_box.pack_end(self._match_label, False, False, 8)

        vbox.pack_end(self._search_box, False, False, 0)

        self.add(vbox)

        # Search entry signals
        self._search_entry.connect("changed", self._on_search_changed)
        self._search_entry.connect("key-press-event", self._on_search_key)

        self._load()
        self.show_all()

        # Search box: realize it via show_all above, then hide immediately
        self._search_box.hide()

        # Grab focus immediately so keys work without clicking first
        GLib.idle_add(self.webview.grab_focus)

    # ── GTK CSS ───────────────────────────────────────

    @staticmethod
    def _apply_gtk_css():
        provider = Gtk.CssProvider()
        provider.load_from_data(GTK_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    # ── Loading ───────────────────────────────────────

    def _load(self):
        html = md_to_html(self.filepath)
        base = f"file://{os.path.dirname(self.filepath)}/"
        self.webview.load_html(html, base)
        self.set_title(os.path.basename(self.filepath))
        self._last_search = ""
        GLib.timeout_add(150, self.webview.grab_focus)

    # ── JS helpers ────────────────────────────────────

    def _js(self, script: str):
        self.webview.evaluate_javascript(script, -1, None, None, None, None, None)

    def _scroll_by(self, px: int):
        self._js(f"window.scrollBy(0,{px})")

    def _scroll_to_top(self):
        self._js("window.scrollTo(0,0)")

    def _scroll_to_bottom(self):
        self._js("window.scrollTo(0,document.body.scrollHeight)")

    # ── Headline navigation ────────────────────────────────

    def _scroll_to_next_heading(self):
        self._js("""
(function() {
    var headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'));
    var scrollY = window.scrollY + 100;
    var found = headings.find(function(h) {
        return h.getBoundingClientRect().top + window.scrollY > scrollY;
    });
    if (found) found.scrollIntoView({behavior: 'smooth', block: 'start'});
})()
""")

    def _scroll_to_prev_heading(self):
        self._js("""
(function() {
    var headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'));
    var scrollY = window.scrollY;
    var prev = headings.filter(function(h) {
        return h.getBoundingClientRect().top + scrollY < scrollY - 50;
    });
    if (prev.length > 0) {
        prev[prev.length - 1].scrollIntoView({behavior: 'smooth', block: 'start'});
    }
})()
""")

    # ── Search ────────────────────────────────────────

    def _open_search(self):
        self._mode = self.MODE_SEARCH
        self._search_box.show()
        self._search_entry.set_text(self._last_search)
        self._search_entry.grab_focus()
        if self._last_search:
            self._search_entry.select_region(0, -1)

    def _close_search(self):
        self._mode = self.MODE_NORMAL
        self._last_search = self._search_entry.get_text()
        self._search_box.hide()
        self.webview.grab_focus()

    def _clear_search(self):
        """Clear search highlights and reset search state."""
        self._find_controller.search_finish()
        self._last_search = ""
        self._match_label.set_text("")

    def _on_search_changed(self, entry):
        text = entry.get_text()
        if text:
            opts = (
                WebKit2.FindOptions.CASE_INSENSITIVE | WebKit2.FindOptions.WRAP_AROUND
            )
            self._find_controller.search(text, opts, 1000)
        else:
            self._find_controller.search_finish()
            self._match_label.set_text("")

    def _on_search_key(self, _widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key == "Escape":
            self._close_search()
            return True
        elif key == "Return":
            self._close_search()
            return True
        return False

    def _search_next(self):
        if self._last_search:
            self._find_controller.search_next()

    def _search_previous(self):
        if self._last_search:
            self._find_controller.search_previous()

    def _on_found_text(self, _controller, match_count):
        if match_count == 1:
            self._match_label.set_text("1 match")
        else:
            self._match_label.set_text(f"{match_count} matches")
        self._match_label.get_style_context().remove_class("search-no-match")
        self._match_label.get_style_context().add_class("search-count")

    def _on_not_found(self, _controller):
        self._match_label.set_text("no matches")
        self._match_label.get_style_context().remove_class("search-count")
        self._match_label.get_style_context().add_class("search-no-match")

    # ── Link hints ─────────────────────────────────────────

    def _show_link_hints(self):
        self._mode = self.MODE_LINK_HINT
        self._link_hint_query = ""
        js = """
(function() {
    document.querySelectorAll('.link-hint').forEach(function(h) { h.remove(); });
    var existing = document.querySelector('.link-hint-input');
    if (existing) existing.remove();

    var links = Array.from(document.querySelectorAll('a[href]')).filter(function(a) {
        var r = a.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight;
    });

    if (links.length === 0) return 0;

    window._hintLinks = links;

    links.forEach(function(link, i) {
        var rect = link.getBoundingClientRect();
        var hint = document.createElement('span');
        hint.className = 'link-hint';
        hint.textContent = i + 1;
        hint.style.left = (rect.left + window.scrollX - 2) + 'px';
        hint.style.top  = (rect.top  + window.scrollY - 16) + 'px';
        document.body.appendChild(hint);
    });

    return links.length;
})()
"""
        self.webview.evaluate_javascript(
            js, -1, None, None, None, self._on_hint_count_ready, None
        )

    def _on_hint_count_ready(self, _source, result, _user_data=None):
        try:
            jsc_value = self.webview.evaluate_javascript_finish(result)
            if jsc_value:
                self._link_hint_count = int(jsc_value.to_double())
            else:
                self._link_hint_count = 0
        except Exception:
            self._link_hint_count = 0

        if self._link_hint_count == 0:
            self._mode = self.MODE_NORMAL

    def _clear_link_hints(self):
        self._mode = self.MODE_NORMAL
        self._js("""
(function() {
    document.querySelectorAll('.link-hint').forEach(function(h) { h.remove(); });
    window._hintLinks = null;
})()
""")
        GLib.idle_add(self.webview.grab_focus)

    def _handle_link_hint_enter(self, override_query=None):
        """Read the number from the query, resolve the URL, open it."""
        query = override_query if override_query else self._link_hint_query
        js = f"""
(function() {{
    var num = parseInt('{query}');
    var links = window._hintLinks;
    var url = '';
    if (num >= 1 && links && num <= links.length) {{
        url = links[num - 1].href;
    }}
    document.querySelectorAll('.link-hint').forEach(function(h) {{ h.remove(); }});
    window._hintLinks = null;
    return url;
}})()
"""
        self._mode = self.MODE_NORMAL
        self.webview.evaluate_javascript(
            js, -1, None, None, None, self._on_hint_url_ready, None
        )

    def _on_hint_url_ready(self, _source, result, _user_data=None):
        try:
            jsc_value = self.webview.evaluate_javascript_finish(result)
            if jsc_value:
                url = jsc_value.to_string()
                if url:
                    subprocess.Popen(["xdg-open", url])
        except Exception:
            pass
        GLib.idle_add(self.webview.grab_focus)

    # ── Zoom ───────────────────────────────────────────

    def _zoom(self, delta: float):
        z = round(self.webview.get_zoom_level() + delta, 2)
        self.webview.set_zoom_level(max(0.3, min(5.0, z)))

    # ── Signals ───────────────────────────────────────

    def _on_resize(self, _w, alloc):
        self._win_height = alloc.height

    def _on_scroll_edge(self, scroll, pos):
        if pos == Gtk.PositionType.BOTTOM:
            self._update_title_with_progress(100)
        elif pos == Gtk.PositionType.TOP:
            self._update_title_with_progress(0)

    def _update_title_with_progress(self, pct):
        if pct is not None:
            self.set_title(f"{os.path.basename(self.filepath)} [{pct}%]")

    def _on_policy(self, _wv, decision, dtype):
        """Never navigate inside the viewer; send links to xdg-open."""
        if dtype == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            action = decision.get_navigation_action()
            uri = action.get_request().get_uri()
            if uri and not uri.startswith("about:") and action.is_user_gesture():
                subprocess.Popen(["xdg-open", uri])
                decision.ignore()
                return True
        return False

    # ── Key handling (modal) ──────────────────────────

    def _on_key(self, _widget, event):
        key = Gdk.keyval_name(event.keyval)

        # ── SEARCH mode: keys go to the GTK Entry ────
        if self._mode == self.MODE_SEARCH:
            if key == "Escape":
                self._close_search()
                return True
            return False

        # ── LINK_HINT mode: keys are captured in Python ──
        if self._mode == self.MODE_LINK_HINT:
            if key == "Escape":
                self._clear_link_hints()
                return True
            if key == "Return":
                self._handle_link_hint_enter()
                return True
            if key == "BackSpace":
                self._link_hint_query = self._link_hint_query[:-1]
                return True

            # Check for digit
            char = event.string
            if char.isdigit():
                self._link_hint_query += char

                # Logic for instant open:
                # 1. How many links START with this query?
                q = self._link_hint_query
                matches = [
                    i + 1
                    for i in range(self._link_hint_count)
                    if str(i + 1).startswith(q)
                ]

                # 2. If exactly one match, and it IS the query, open it.
                # OR if no other links COULD possibly match with more digits (e.g. q='2' and target=12)
                if len(matches) == 1 and str(matches[0]) == q:
                    self._handle_link_hint_enter()
                elif len(matches) == 0:
                    # No such link, reset
                    self._link_hint_query = ""

                return True
            return True  # Swallow other keys in hint mode

        # ── NORMAL mode ──────────────────────────────
        half = max(100, self._win_height // 2 - 40)

        if key == "q":
            Gtk.main_quit()
        elif key == "slash":
            self._open_search()
        elif key == "o":
            self._show_link_hints()
        elif key == "n":
            self._search_next()
        elif key == "p":
            self._search_previous()
        elif key == "Escape":
            self._clear_search()
        elif key in ("j", "Down"):
            self._scroll_by(self.SCROLL_STEP)
        elif key in ("k", "Up"):
            self._scroll_by(-self.SCROLL_STEP)
        elif key == "d":
            self._scroll_by(half)
        elif key == "u":
            self._scroll_by(-half)
        elif key in ("g", "Home"):
            self._scroll_to_top()
        elif key in ("G", "End"):
            self._scroll_to_bottom()
        elif key in ("plus", "equal"):
            self._zoom(self.ZOOM_STEP)
        elif key == "minus":
            self._zoom(-self.ZOOM_STEP)
        elif key == "0":
            self.webview.set_zoom_level(1.0)
        elif key == "r":
            self._load()
        elif key in ("f", "F11"):
            if self.fullscreen_on:
                self.unfullscreen()
                self.fullscreen_on = False
            else:
                self.fullscreen()
                self.fullscreen_on = True
        elif key == "braceleft":
            self._scroll_to_prev_heading()
        elif key == "braceright":
            self._scroll_to_next_heading()
        else:
            return False

        return True


# ── Desktop Integration ──────────────────────────────────────────


def install_desktop_entry():
    """Generates a .desktop entry and icon in the user's local directory."""
    print("Installing desktop entry and icon...")

    # 1. Determine local paths
    home = Path.home()
    apps_dir = home / ".local/share/applications"
    icons_dir = home / ".local/share/icons"

    apps_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    icon_path = icons_dir / "mdread.webp"
    desktop_path = apps_dir / "mdread.desktop"

    # 2. Copy Icon from package data
    try:
        # Find the icon inside the installed package
        icon_source = resources.files("mdread") / "mdread.webp"
        if icon_source.is_file():
            with icon_source.open("rb") as f_src:
                with open(icon_path, "wb") as f_dst:
                    shutil.copyfileobj(f_src, f_dst)
            print(f"Icon installed to: {icon_path}")
        else:
            # Fallback for local repository execution
            repo_icon = Path(__file__).parent / "mdread.webp"
            if repo_icon.exists():
                shutil.copy(repo_icon, icon_path)
                print(f"Icon installed (from script dir) to: {icon_path}")
            else:
                print(
                    "Warning: Could not find mdread.webp in package or script directory."
                )
    except Exception as e:
        print(f"Error saving icon: {e}")
        return

    # 3. Find binary
    binary = shutil.which("mdread")
    if not binary:
        # Fallback to current script if not in path (e.g. running from repo)
        binary = os.path.abspath(sys.argv[0])
        print(f"Warning: 'mdread' not found in PATH. Using: {binary}")

    # 4. Write Desktop File
    desktop_content = f"""[Desktop Entry]
Type=Application
Name=mdread
Comment=No-frills keyboard-driven Markdown reader
Exec={binary} %f
Icon={icon_path}
Terminal=false
Categories=Utility;TextTools;
MimeType=text/markdown;text/x-markdown;
Keywords=markdown;reader;viewer;vesper;
"""
    try:
        with open(desktop_path, "w") as f:
            f.write(desktop_content)
        print(f"Successfully created: {desktop_path}")
    except Exception as e:
        print(f"Error creating desktop entry: {e}")


def main():
    parser = argparse.ArgumentParser(
        prog="mdread",
        description="Minimal keyboard-driven Markdown reader.",
    )
    parser.add_argument("file", nargs="?", help="Markdown file to open")
    parser.add_argument(
        "--install-desktop",
        action="store_true",
        help="Install desktop entry and icon to ~/.local/share",
    )
    args = parser.parse_args()

    # Handle desktop installation
    if args.install_desktop:
        install_desktop_entry()
        sys.exit(0)

    # Regular file loading
    if not args.file:
        parser.print_help()
        sys.exit(0)

    if not os.path.isfile(args.file):
        print(f"mdread: '{args.file}': no such file", file=sys.stderr)
        sys.exit(1)

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    MarkdownReader(args.file)
    Gtk.main()


if __name__ == "__main__":
    main()
