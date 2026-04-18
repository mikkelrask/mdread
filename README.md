# mdread


A minimal, keyboard-driven Markdown reader for Linux. 

Inspired by tools like `zathura` and `sxiv`, `mdread` focuses on reading performance and terminal-style navigation. It's opinionated and minimal. No light mode, no selection of themes, no editing, no frills.


## Features

- **Modal Navigation**: Vim-style modal navigation (Normal, Search, Link-hints).
- **Incremental Search**: Native WebKit search with highlight-as-you-type.
- **Link Hints**: Hit `o` to show numbered hints and instantly open links in browser.
- **Smooth Scrolling**: Via keyboard or mouse.
- **Heading Jumps**: Jump between sections with `{` and `}`.

<img src="https://raw.githubusercontent.com/mikkelrask/mdread/main/img/screenshot.png" alt="mdread readme in mdread" style="margin: 0 auto; display: block;">

## Usage

```bash
mdread file.md
```

## Keybindings

| Key | Action |
|-----|--------|
| `j` / `Down` | Scroll down |
| `k` / `Up` | Scroll up |
| `d` / `u` | Half page down / up |
| `g` / `G` | Top / Bottom of document |
| `{` / `}` | Previous / Next heading |
| `/` | Open Search |
| `n` / `p` | Next / Previous search match |
| `o` | Show Link Hints |
| `r` | Reload file |
| `f` / `F11` | Toggle Fullscreen |
| `+` / `-` / `0` | Zoom In / Out / Reset |
| `q` | Quit |

## Installation

### Dependencies
Since this uses GTK and WebKit, you need the system introspection libraries:

```bash
python-gobject
webkit2gtk-4.1 
```

and the `markdown` and `pygments` python packages:

```bash
pip install markdown pygments
```

### Standard Installation
The recommended way to install `mdread` as a standalone app is via **`pipx`**:

```bash
# Install pipx if you don't have it
pipx install .
```

### Desktop Integration
To make `mdread` appear in your application menu and associate it with Markdown files, run:

```bash
mdread --install-desktop
```

This will install a `.desktop` entry and a custom icon to your local user directory (`~/.local/share`).

### Development Installation
If you want to work on the code, change color scheme, fonts etc:

```bash
# Using a standard virtualenv
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

This will install mdread in your virtual environment. You can then just rerun `mdread file.md` to see your changes.

## Inspiration / Credits
- The idea is inspired by [Mikkel Malmberg / @mikker](https://mikkelmalmberg.com/notes/01KPDNG8AM723KW4YJXRS890C1) and his exciting AI driven software adventures
- Color scheme is based on **Vesper** by [Rauno Freiberg](https://rauno.me/) of Vercel
- Fonts used: **Literata** and **JetBrains Mono** from [Google Fonts](https://fonts.google.com/)

<img src="src/mdread/mdread.webp" alt="mdread" width="200" height="200" style="margin: 0 auto; display: block;">