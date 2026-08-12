# -*- coding: utf-8 -*-
__title__ = 'Batch Rename Families'

# Imports
import clr
import webbrowser

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")

from Autodesk.Revit.DB import FilteredElementCollector, Family, Transaction
from System.Windows import MessageBox, MessageBoxButton, MessageBoxImage
from System.Windows.Controls import ListBoxItem

from pyrevit import forms, script, revit

output = script.get_output()
doc    = revit.doc

ALL_CATEGORIES = "(All Categories)"


# ─────────────────────────────────────────────────────────────────────────────
# COLLECT FAMILIES FROM THE ACTIVE DOCUMENT
# ─────────────────────────────────────────────────────────────────────────────

def collect_families(document):
    """
    Return a sorted list of (name, category_name, Family) tuples.
    Families with no FamilyCategory are placed under '(No Category)'.
    """
    collector = FilteredElementCollector(document).OfClass(Family)
    families  = []
    for fam in collector:
        try:
            name = fam.Name
            if not name:
                continue
            try:
                cat = fam.FamilyCategory
                cat_name = cat.Name if cat is not None else "(No Category)"
            except Exception:
                cat_name = "(No Category)"
            families.append((name, cat_name, fam))
        except Exception:
            pass
    return sorted(families, key=lambda x: (x[1].lower(), x[0].lower()))


def unique_categories(families):
    """Return sorted list of unique category names from the family list."""
    cats = sorted(set(cat for (_, cat, _) in families), key=lambda s: s.lower())
    return [ALL_CATEGORIES] + cats


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

class RenameFamiliesDialog(forms.WPFWindow):

    # ── init ──────────────────────────────────────────────────────────────────

    def __init__(self, families):
        """
        :param families: list of (name, category_name, Family) tuples, sorted.
        """
        super(RenameFamiliesDialog, self).__init__("UI.xaml")

        from System.Windows import WindowStyle
        self.WindowStyle = WindowStyle.SingleBorderWindow
        self.WindowStyle = WindowStyle.None

        self.result  = None
        self._all    = families        # full list: (name, cat, Family)
        self._shown  = list(families)  # currently filtered view
        self._frame  = None            # DispatcherFrame used by show_modal()

        # Populate category combo
        for cat in unique_categories(families):
            self.category_combo.Items.Add(cat)
        self.category_combo.SelectedIndex = 0

        # Wire events AFTER controls are initialised
        self.TitleBar.MouseLeftButtonDown    += self.title_bar_drag
        self.btn_minimize.Click              += self.minimize_click
        self.btn_close.Click                 += self.close_click
        self.btn_cancel.Click                += self.cancel_click
        self.ok_btn.Click                    += self.ok_click
        self.btn_select_all.Click            += self.select_all_click
        self.btn_select_none.Click           += self.select_none_click
        self.category_combo.SelectionChanged += self.filters_changed
        self.filter_box.TextChanged          += self.filters_changed
        self.family_list.SelectionChanged    += self.selection_changed
        self.mode_combo.SelectionChanged     += self.mode_changed
        self.logo.MouseLeftButtonDown        += self.on_image_click

        self._populate_list(self._all)

    # ── filtering ─────────────────────────────────────────────────────────────

    def _active_category(self):
        item = self.category_combo.SelectedItem
        if item is None:
            return ALL_CATEGORIES
        return str(item)

    def filters_changed(self, sender, args):
        """Re-apply both filters whenever either control changes."""
        cat   = self._active_category()
        query = self.filter_box.Text.strip().lower()

        self._shown = [
            (n, c, f) for (n, c, f) in self._all
            if (cat == ALL_CATEGORIES or c == cat)
            and (not query or query in n.lower())
        ]
        self._populate_list(self._shown)
        self._refresh_rename_panel()

    # ── list population ───────────────────────────────────────────────────────

    def _populate_list(self, families):
        """Rebuild the ListBox. Each item shows 'Name  [Category]'."""
        self.family_list.Items.Clear()
        cat = self._active_category()
        for (name, cat_name, fam) in families:
            item         = ListBoxItem()
            # Show category tag only when 'All Categories' is selected
            if cat == ALL_CATEGORIES:
                item.Content = u"{}   —  {}".format(name, cat_name)
            else:
                item.Content = name
            item.Tag     = (name, fam)   # raw name + Family object
            self.family_list.Items.Add(item)
        self._update_counter()

    # ── select helpers ────────────────────────────────────────────────────────

    def select_all_click(self, sender, args):
        self.family_list.SelectAll()

    def select_none_click(self, sender, args):
        self.family_list.UnselectAll()

    # ── selection changed ─────────────────────────────────────────────────────

    def selection_changed(self, sender, args):
        self._update_counter()
        self._refresh_rename_panel()

    def _update_counter(self):
        n = self.family_list.SelectedItems.Count
        shown = self.family_list.Items.Count
        self.selection_label.Text = "{} of {} famil{} selected".format(
            n, shown, "y" if shown == 1 else "ies"
        )

    def _selected_items(self):
        """Return list of (raw_name, Family) for selected ListBoxItems."""
        result = []
        for item in self.family_list.SelectedItems:
            try:
                result.append(item.Tag)   # (name, Family)
            except Exception:
                pass
        return result

    # ── rename panel ──────────────────────────────────────────────────────────

    def _refresh_rename_panel(self):
        from System.Windows import Visibility
        selected = self._selected_items()
        n = len(selected)

        if n == 0:
            self.single_panel.Visibility = Visibility.Collapsed
            self.multi_panel.Visibility  = Visibility.Collapsed
            self.ok_btn.IsEnabled        = False

        elif n == 1:
            self.single_panel.Visibility = Visibility.Visible
            self.multi_panel.Visibility  = Visibility.Collapsed
            self.current_name_box.Text   = selected[0][0]
            self.new_name_box.Text       = selected[0][0]
            self.ok_btn.IsEnabled        = True

        else:
            self.single_panel.Visibility = Visibility.Collapsed
            self.multi_panel.Visibility  = Visibility.Visible
            self.ok_btn.IsEnabled        = True
            self._update_preview()

    # ── mode combo ────────────────────────────────────────────────────────────

    def mode_changed(self, sender, args):
        from System.Windows import Visibility
        idx = self.mode_combo.SelectedIndex
        self.find_replace_panel.Visibility = (
            Visibility.Visible if idx == 0 else Visibility.Collapsed
        )
        self.prefix_panel.Visibility = (
            Visibility.Visible if idx == 1 else Visibility.Collapsed
        )
        self.suffix_panel.Visibility = (
            Visibility.Visible if idx == 2 else Visibility.Collapsed
        )
        self._update_preview()

    # ── preview ───────────────────────────────────────────────────────────────

    def _compute_new_name(self, original):
        idx = self.mode_combo.SelectedIndex
        if idx == 0:   # Find & Replace
            find = self.find_box.Text
            return original.replace(find, self.replace_box.Text) if find else original
        elif idx == 1:  # Prefix
            return self.prefix_box.Text + original
        else:           # Suffix
            return original + self.suffix_box.Text

    def _update_preview(self):
        selected = self._selected_items()
        if not selected:
            self.preview_label.Text = ""
            return
        lines = []
        for (name, _) in selected[:3]:
            new = self._compute_new_name(name)
            lines.append(u"{}  →  {}".format(name, new))
        if len(selected) > 3:
            lines.append(u"… and {} more".format(len(selected) - 3))
        self.preview_label.Text = u"\n".join(lines)

    # ── ok / cancel ───────────────────────────────────────────────────────────

    def ok_click(self, sender, args):
        selected = self._selected_items()
        if not selected:
            MessageBox.Show("No families selected.",
                            "Validation", MessageBoxButton.OK,
                            MessageBoxImage.Warning)
            return

        plan = []   # [(Family, new_name)]

        if len(selected) == 1:
            new_name = self.new_name_box.Text.strip()
            if not new_name:
                MessageBox.Show("New name cannot be empty.",
                                "Validation", MessageBoxButton.OK,
                                MessageBoxImage.Warning)
                return
            plan.append((selected[0][1], new_name))
        else:
            for (name, fam) in selected:
                new_name = self._compute_new_name(name).strip()
                if new_name:
                    plan.append((fam, new_name))

        # Validate: no empty names
        if any(not nn for (_, nn) in plan):
            MessageBox.Show(
                "One or more computed names are empty.\n"
                "Please adjust the rename settings.",
                "Validation", MessageBoxButton.OK, MessageBoxImage.Warning)
            return

        # Validate: no duplicates within the plan
        new_names = [nn for (_, nn) in plan]
        if len(new_names) != len(set(nn.lower() for nn in new_names)):
            MessageBox.Show(
                "The rename operation would produce duplicate family names.\n"
                "Please adjust the settings.",
                "Validation", MessageBoxButton.OK, MessageBoxImage.Warning)
            return

        # Validate: no conflict with existing families not being renamed
        being_renamed_ids = set(f.Id.IntegerValue for (f, _) in plan)
        existing_lower    = set(
            n.lower() for (n, _, f) in self._all
            if f.Id.IntegerValue not in being_renamed_ids
        )
        conflicts = [nn for nn in new_names if nn.lower() in existing_lower]
        if conflicts:
            MessageBox.Show(
                u"The following name(s) already exist in the project:\n\n"
                + u"\n".join(conflicts[:10])
                + (u"\n…" if len(conflicts) > 10 else u""),
                "Name Conflict", MessageBoxButton.OK, MessageBoxImage.Warning)
            return

        self.result = plan
        self.Close()

    def title_bar_drag(self, sender, args):
        self.DragMove()

    def on_image_click(self, sender, event_args):
        """Handle the image click event to open a URL."""
        url = "https://www.pambuilding.co.uk"
        webbrowser.open(url)

    def minimize_click(self, sender, args):
        from System.Windows import WindowState
        self.WindowState = WindowState.Minimized

    def close_click(self, sender, args):
        self._stop_frame()
        self.Close()

    def cancel_click(self, sender, args):
        self._stop_frame()
        self.Close()

    def _stop_frame(self):
        """Release the DispatcherFrame so show_modal() returns."""
        if self._frame is not None:
            self._frame.Continue = False
            self._frame = None

    def show_modal(self):
        from System.Windows.Threading import Dispatcher, DispatcherFrame
        from System.Windows.Interop import WindowInteropHelper
        from System.Windows import SystemParameters

        # Attach to Revit's main window so minimize is independent of Revit
        helper = WindowInteropHelper(self)
        helper.Owner = revit.HOST_APP.uiapp.MainWindowHandle

        # Center horizontally using the fixed Width set in XAML, 60 px from top
        self.Left = (SystemParameters.PrimaryScreenWidth - self.Width) / 2
        self.Top  = 140   # px from top — adjust to taste

        self._frame = DispatcherFrame()
        self.Closed += lambda s, e: self._stop_frame()
        self.Show()
        Dispatcher.PushFrame(self._frame)  # blocks here until _stop_frame()


# ─────────────────────────────────────────────────────────────────────────────
# APPLY RENAMES
# ─────────────────────────────────────────────────────────────────────────────

def apply_renames(document, plan):
    n_ok, n_err = 0, 0
    with Transaction(document, "Rename Families") as t:
        t.Start()
        for (fam, new_name) in plan:
            try:
                old_name = fam.Name
                fam.Name = new_name
                n_ok += 1
                output.print_md(u"&#x2714; `{}` &rarr; `{}`".format(old_name, new_name))
            except Exception as ex:
                n_err += 1
                output.print_md(u"&#x2716; `{}` &mdash; {}".format(fam.Name, str(ex)))
        t.Commit()
    return n_ok, n_err


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    families = collect_families(doc)

    if not families:
        forms.alert(
            "No families found in the active document.",
            title="Nothing to rename"
        )
        script.exit()

    dlg = RenameFamiliesDialog(families)
    dlg.show_modal()

    if dlg.result is None:
        script.exit()

    plan = dlg.result

    output.print_md(
        "## Rename Families\n\n"
        "**{}** famil{} queued for renaming.\n\n---"
        .format(len(plan), "y" if len(plan) == 1 else "ies")
    )

    n_ok, n_err = apply_renames(doc, plan)

    output.print_md(
        "\n---\n**Renamed:** {}  &nbsp;&middot;&nbsp;  **Errors:** {}"
        .format(n_ok, n_err)
    )

    if n_err:
        forms.alert(
            "{} famil{} could not be renamed.\n"
            "Check the output window for details."
            .format(n_err, "y" if n_err == 1 else "ies"),
            title="Rename completed with errors"
        )


if __name__ == "__main__":
    main()