# -*- coding: utf-8 -*-
import os
import clr
import webbrowser

# Add references to the necessary assemblies
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')

from System.Windows.Controls import Button, TextBox, Image, ListBox
from System.Windows.Input import MouseButtonState

# Import required classes from Revit API
from pyrevit import revit, script, forms
from pyrevit.forms import WPFWindow

#import Autodesk
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.Exceptions import OperationCanceledException

from System.Collections.Generic import List

# Variables
doc = revit.doc
uidoc = revit.uidoc

# Custom class to represent a category item in the ListBox
class CategoryItem:
    """Class to represent a category item in the ListBox."""
    def __init__(self, category):
        self.Category = category
        self.IsChecked = False
        self.Name = category.Name

# Collect all categories available in the project and create a list of CategoryItem objects
category_items = {}
categories = doc.Settings.Categories

for category in categories:
    if isinstance(category, Category) and category.CategoryType == CategoryType.Model:
        category_key = category.Name
        if category_key not in category_items:
            category_items[category_key] = CategoryItem(category)

# Sort the category items by Name
sorted_category_items = sorted(category_items.values(), key=lambda item: item.Name)

# Define a selection filter to allow the user to select only elements of selected categories
class CategorySelectionFilter(ISelectionFilter):
    def __init__(self, category_names):
        self.category_names = category_names

    def AllowElement(self, element):
        if element.Category is not None and element.Category.Name in self.category_names:
            return True
        else:
            return False
        
    def AllowReference(self, ref, point):
        return True

def show_window(category_items):
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
        list_box = window.FindName('list_categories')
        if list_box:
            selected_items = [item for item in list_box.Items if isinstance(item, CategoryItem) and item.IsChecked]
            if not selected_items:
                forms.alert('Please select at least one category', title='Select Categories')
                return

        # Set the flag to indicate the run button was clicked
        run_button_clicked[0] = True  

        # Close the window and return selected data
        window.DialogResult = True
        window.Categories = [item.Category for item in list_box.Items if isinstance(item, CategoryItem) and item.IsChecked]
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
        list_box = window.FindName('list_categories')
        if list_box and isinstance(list_box, ListBox):
            for item in list_box.Items:
                if isinstance(item, CategoryItem):
                    item.IsChecked = True
            list_box.Items.Refresh()  # Refresh the ListBox to reflect changes

    def uncheck_all_click(sender, args):
        """Handle the uncheck all button click event."""
        list_box = window.FindName('list_categories')
        if list_box and isinstance(list_box, ListBox):
            for item in list_box.Items:
                if isinstance(item, CategoryItem):
                    item.IsChecked = False
            list_box.Items.Refresh()  # Refresh the ListBox to reflect changes

    def UI_text_filter_updated(sender, args):
        """Handle TextBox TextChanged event to filter ListBox items."""
        filter_text = sender.Text.lower()
        list_box = window.FindName('list_categories')
        list_box.Items.Clear()
        for item in category_items:
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

    # Populate ListBox with categories
    list_box = window.FindName('list_categories')
    if list_box and isinstance(list_box, ListBox):
        for category_item in category_items:
            list_box.Items.Add(category_item)

    # Show the window
    window.ShowDialog()

    # Retrieve and return selected categories
    if window.DialogResult:
        return window.Categories, run_button_clicked[0]
    else:
        return None, run_button_clicked[0]

def main():
    selected_categories, run_button_clicked = show_window(sorted_category_items)

    if not run_button_clicked:
        script.exit()

    if not selected_categories:
        forms.alert('No categories selected', title='Select Categories')
        script.exit()

    # Get the selected category names
    selected_category_names = [category.Name for category in selected_categories]

    # List to retain the selected elements directly
    retained_selection = []

    while True:
        try:
            with forms.WarningBar(title='Select elements and press Finish when complete'):
                filter = CategorySelectionFilter(selected_category_names)
                selected_ids = uidoc.Selection.PickObjects(ObjectType.Element, filter, 'Select Elements')
                
                # Retrieve elements from the selection
                new_selected_elements = [doc.GetElement(id.ElementId) for id in selected_ids]
                retained_selection.extend(new_selected_elements)

                # Only use the ElementIds for setting the selection in Revit
                retained_element_ids = List[ElementId]([elem.Id for elem in retained_selection])
                uidoc.Selection.SetElementIds(retained_element_ids)
            
        except OperationCanceledException:
            forms.alert('User cancelled selection', title='Select elements')
        break
if __name__ == '__main__':
    main()
