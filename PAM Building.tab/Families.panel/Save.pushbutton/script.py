# -*- coding: utf-8 -*-
__title__ = 'Batch Save\nFamilies'

# Import required classes and add references to required libraries
import os
import clr
import webbrowser

clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')

from System.Windows.Controls import Button, TextBox, Image, ListBox
from System.Windows.Input import MouseButtonState

from pyrevit import revit, script, forms
from pyrevit.forms import WPFWindow

from Autodesk.Revit.Exceptions import OperationCanceledException

# Get document
doc = revit.doc

# Custom class to represent an item in the ListBox
class FamilyItem:
    """Class to represent a family item in the ListBox."""
    def __init__(self, family, category_name):
        self.Family = family
        self.IsChecked = False
        self.Name = "{}: {}".format(category_name, family.Name)

# Collect families and create a list of FamilyItem objects
family_items = {}
for family in revit.query.get_families(revit.doc, only_editable=True):
    if family.FamilyCategory:
        family_key = "{}: {}".format(family.FamilyCategory.Name, family.Name)
        if family_key not in family_items:
            family_items[family_key] = FamilyItem(family, family.FamilyCategory.Name)

# Sort the family items by Name
sorted_family_items = sorted(family_items.values(), key=lambda item: item.Name)

def show_window(family_items):
    """Load and display the WPF window for user interaction."""
    # Path to your XAML file relative to the script directory
    script_dir = os.path.dirname(__file__)
    xaml_file_path = os.path.join(script_dir, 'UI.xaml')

    # Load the WPF window from the XAML file
    window = WPFWindow(xaml_file_path)

    run_button_clicked = [False]  # Use a list to hold the flag so it can be modified in the nested functions

    def close_button_click(sender, args):
        """Handle the close button click event."""
        window.Close()

    def run_button_click(sender, args):
        """Handle the run button click event."""
        list_box = window.FindName('list_families')
        if list_box:
            selected_items = [item for item in list_box.Items if isinstance(item, FamilyItem) and item.IsChecked]
            if not selected_items:
                forms.alert('Please select at least one family', title='Select Families')
                return

        # Set the flag to indicate the run button was clicked
        run_button_clicked[0] = True  

        # Close the window and return selected data
        window.DialogResult = True
        window.Family = [item.Family for item in list_box.Items if isinstance(item, FamilyItem) and item.IsChecked]
        window.Close()

    def on_image_click(sender, event_args):
        """Handle the image click event to open a URL."""
        url = "https://www.pambuilding.co.uk"
        webbrowser.open(url)

    def header_drag(sender, event_args):
        """Allow dragging the window by the header."""
        if event_args.LeftButton == MouseButtonState.Pressed:
            window.DragMove()

    def check_all_click(sender, args):
        """Handle the check all button click event."""
        list_box = window.FindName('list_families')
        if list_box and isinstance(list_box, ListBox):
            for item in list_box.Items:
                if isinstance(item, FamilyItem):
                    item.IsChecked = True
            list_box.Items.Refresh()  # Refresh the ListBox to reflect changes

    def uncheck_all_click(sender, args):
        """Handle the uncheck all button click event."""
        list_box = window.FindName('list_families')
        if list_box and isinstance(list_box, ListBox):
            for item in list_box.Items:
                if isinstance(item, FamilyItem):
                    item.IsChecked = False
            list_box.Items.Refresh()  # Refresh the ListBox to reflect changes
    
    def UI_text_filter_updated(sender, args):
        """Handle TextBox TextChanged event to filter ListBox items."""
        filter_text = sender.Text.lower()
        list_box = window.FindName('list_families')
        list_box.Items.Clear()
        for item in family_items:
            if filter_text in item.Name.lower():
                list_box.Items.Add(item)

    # Attach event handlers
    close_button = window.FindName('button_close')
    if close_button and isinstance(close_button, Button):
        close_button.Click += close_button_click

    run_button = window.FindName('button_run')
    if run_button and isinstance(run_button, Button):
        run_button.Click += run_button_click

    check_all_button = window.FindName('button_check_all')
    if check_all_button and isinstance(check_all_button, Button):
        check_all_button.Click += check_all_click

    uncheck_all_button = window.FindName('button_uncheck_all')
    if uncheck_all_button and isinstance(uncheck_all_button, Button):
        uncheck_all_button.Click += uncheck_all_click

    # Attach the image click event handler
    image = window.FindName('logo')
    if image and isinstance(image, Image):
        image.MouseLeftButtonDown += on_image_click

    # Find the TitleBar and attach the drag event handler
    title_bar = window.FindName('TitleBar')
    if title_bar:
        title_bar.MouseLeftButtonDown += header_drag

    # Attach the TextChanged event handler to the TextBox in code
    text_box = window.FindName('textbox_filter')
    if text_box and isinstance(text_box, TextBox):
        text_box.TextChanged += UI_text_filter_updated

    # Populate ListBox with families
    list_box = window.FindName('list_families')
    if list_box and isinstance(list_box, ListBox):
        for family_item in family_items:
            list_box.Items.Add(family_item)

    # Show the window
    window.ShowDialog()

    # Retrieve and return selected families
    if window.DialogResult:
        return window.Family, run_button_clicked[0]
    else:
        return None, run_button_clicked[0]

# Show the custom window and get selected families
selected_families, run_button_clicked = show_window(sorted_family_items)

if not run_button_clicked:
    script.exit()

if not selected_families:
    forms.alert('No families selected', title='Select Families')
    script.exit()

# Proceed with folder selection
try:
    folder_path = forms.pick_folder()
except OperationCanceledException:
    forms.alert('User cancelled', title='Error')
    script.exit()

# Check if a folder was selected
if folder_path:
    num_saved = 0  # Counter variable
    for family in selected_families:
        family_name = family.Name
        fam_doc = doc.EditFamily(family)
        fam_doc.SaveAs(os.path.join(folder_path, family_name + ".rfa"))
        fam_doc.Close(False)
        num_saved += 1  # Increment the counter

    forms.alert(
        "Nice work, you saved {} families in {}".format(num_saved, folder_path),
        title='Success'
    )
else:
    forms.alert('No folder selected', title='Select Folder')
