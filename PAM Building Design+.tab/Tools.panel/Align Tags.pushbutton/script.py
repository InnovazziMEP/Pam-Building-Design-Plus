# -*- coding: utf-8 -*-
__title__ = "Align Tags"

# Imports
import os
import clr
import webbrowser

# Add references to the necessary assemblies
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference("System")

# System imports
from System.Windows.Controls import Button, Image, ListBox
from System.Windows.Input import MouseButtonState

# Add references to required Revit API libraries
clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

# Import required classes from Revit API
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *

#pyRevit imports
from pyrevit import revit, forms, script
from pyrevit.forms import WPFWindow

# Variables
doc = revit.doc
uidoc = revit.uidoc

class TagItem:
    """Class to represent a tag item in the ListBox."""
    def __init__(self, tag):
        self.Tag = tag
        self.IsChecked = False
        # Ensure 'tag' has 'Name' attribute
        if hasattr(tag, 'Name'):
            self.Name = "{}".format(tag.Name)
        else:
            self.Name = "{}".format(tag)

# Function to get all loaded tag families dynamically
def get_loaded_tag_families(doc):
    loaded_tags = set()

    # Collect all family symbols
    collector = FilteredElementCollector(doc).OfClass(FamilySymbol)

    for symbol in collector:
        # Check if the symbol is a tag
        if symbol.Category and "Tag" in symbol.Category.Name:
            loaded_tags.add(symbol.Category.Name)

    return sorted(loaded_tags)

def show_window(loaded_tags):
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
        list_box = window.FindName('list_tags')
        if list_box:
            selected_tags = [item.Tag for item in list_box.Items if isinstance(item, TagItem) and item.IsChecked]
            if not selected_tags:
                forms.alert('Please select at least one tag type', title='Select Tag Type')
                return
        
        # Set the flag to indicate the run button was clicked
        run_button_clicked[0] = True  
        
        # Close the window and return selected data
        window.DialogResult = True
        window.Tag = selected_tags
        window.Close()

    def on_image_click(sender, event_args):
        """Handle the image click event to open a URL."""
        url = "https://www.pambuilding.co.uk/"
        webbrowser.open(url)

    def header_drag(sender, event_args):
        """Allow dragging the window by the header."""
        if event_args.LeftButton == MouseButtonState.Pressed:
            window.DragMove()

    def check_all_click(sender, args):
        """Handle the check all button click event."""
        list_box = window.FindName('list_tags')
        if list_box and isinstance(list_box, ListBox):
            for item in list_box.Items:
                if isinstance(item, TagItem):
                    item.IsChecked = True
            list_box.Items.Refresh()  # Refresh the ListBox to reflect changes

    def uncheck_all_click(sender, args):
        """Handle the uncheck all button click event."""
        list_box = window.FindName('list_tags')
        if list_box and isinstance(list_box, ListBox):
            for item in list_box.Items:
                if isinstance(item, TagItem):
                    item.IsChecked = False
            list_box.Items.Refresh()  # Refresh the ListBox to reflect changes

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

    # Populate ListBox with tags
    list_box = window.FindName('list_tags')
    if list_box and isinstance(list_box, ListBox):
        tags = get_loaded_tag_families(doc)
        for tag in tags:
            list_box.Items.Add(TagItem(tag))

    # Show the window
    window.ShowDialog()

    # Retrieve and return selected tags
    if window.DialogResult:
        return window.Tag, run_button_clicked[0]
    else:
        return None, run_button_clicked[0]

"""# Check if active view is valid for the script to run
cView = doc.ActiveView
if cView.ViewType not in [ViewType.FloorPlan, ViewType.CeilingPlan, ViewType.AreaPlan]:
    forms.alert('This tool only works in Floor, Ceiling, or Area Plan Views', title='Change View')
    script.exit()"""

# Get the loaded tag families
loaded_tag_families = get_loaded_tag_families(doc)

# Show the custom window and get selected tags
selected_tags, run_button_clicked = show_window(loaded_tag_families)

# If the Close button was clicked, do nothing
if not run_button_clicked:
    script.exit()

if not selected_tags:
    forms.alert('No tags selected', title='Select Tags')
    script.exit()

# Define a selection filter to select only the selected tags from the form
class TagSelectionFilter(ISelectionFilter):
    def __init__(self, allowed_tag_categories):
        self.allowed_tag_categories = allowed_tag_categories

    def AllowElement(self, elem):
        if elem.Category.Name in self.allowed_tag_categories:
            return True
        else:
            return False

    def AllowReference(self, ref, point):
        return True

# Function to select tags
def select_tags():
    while True: # Loop to keep the selection filter active
        try:
            with forms.WarningBar(title='Select tags and press Finish when complete'):
                selection = uidoc.Selection
                tag_filter = TagSelectionFilter(selected_tags)
                selected_elements = selection.PickObjects(ObjectType.Element, tag_filter, "Select tags")
                
                # Check if any elements were selected
                if not selected_elements:
                    forms.alert('No tags selected', title='Select Tags')
                    continue

            if selected_elements:
                # Get the tags as Element objects
                tags = [doc.GetElement(obj.ElementId) for obj in selected_elements]
                return tags
            else:
                return None
        except OperationCanceledException:
                    # Handle the case when selection is canceled by the user (ESC pressed)
                    forms.alert('User cancelled tag selection', title='Select Tags')
        script.exit()

# Get dimensions of selected tags
# Move them to the X coordinate of the selected point, distribute them evenly on vertical and set leader elbows
def arrange_tags_vertically():
    try:
        # Get selected tags
        tags = select_tags()

        # Get a point to align the tags to
        with forms.WarningBar(title='Select a point to align the tags to or press ESC to cancel'):
            try:
                selected_point = uidoc.Selection.PickPoint()
            except OperationCanceledException:
                forms.alert('User cancelled point selection', title='Select Point')
                script.exit()

        # Start a transaction group
        with TransactionGroup(doc, __title__) as tg_outer:
            tg_outer.Start()
            # Start a transaction to set the Leader Type parameter
            with revit.Transaction("Set Tag Leader Type"):
                # Loop through the selected tags and set the Leader Type parameter to Free End
                for tag in tags:
                    tag.LeaderEndCondition = LeaderEndCondition.Free

            # Get the view and right/up direction vectors
            view = doc.GetElement(tag.OwnerViewId)
            up_direction = view.UpDirection

            # Define a transaction group and start a transaction to get the dimensions of the tags
            with TransactionGroup(doc, "Get Tag Dimensions") as tg_inner:
                tg_inner.Start()

                # Start a new transaction for modifying the tag
                with Transaction(doc, "Get Tag Dimensions") as t:
                    t.Start()
                    for tag in tags:
                        # Modify the tag to determine its extents
                        elem_reference = tag.GetTaggedReferences()[0]
                        leader_end_point = tag.GetLeaderEnd(elem_reference)
                        tag.TagHeadPosition = leader_end_point
                        tag.SetLeaderElbow(elem_reference, leader_end_point)

                    t.Commit()

                # Determine the dimensions of the tag
                bbox = tag.get_BoundingBox(view)
                tag_height = (bbox.Max - bbox.Min).DotProduct(up_direction)

                # Roll back the transaction group
                tg_inner.RollBack()

            # Start a transaction to move and align the tags vertically
            with revit.Transaction("Move and align tags vertically"):
                # Get X coordinate to move the tags to
                x_coord = selected_point.X

                # Move the tags to the X coordinate of the selected point
                for tag in tags:
                    tag_head_position = tag.TagHeadPosition
                    new_location = XYZ(x_coord, tag_head_position.Y, tag_head_position.Z)
                    tag.TagHeadPosition = new_location

                # Sort the tags by their Y coordinate
                sorted_tags = sorted(tags, key=lambda tag: tag.TagHeadPosition.Y)

                # Calculate the vertical distance between the tags
                tag_distance = (sorted_tags[-1].TagHeadPosition.Y - sorted_tags[0].TagHeadPosition.Y) / (
                            len(sorted_tags) - 1)

                # Distribute the tags evenly on vertical
                for index, tag in enumerate(sorted_tags):
                    new_location = XYZ(x_coord, sorted_tags[0].TagHeadPosition.Y + index * tag_distance,
                                       sorted_tags[0].TagHeadPosition.Z)
                    tag.TagHeadPosition = new_location

                    # Set leader elbow position for the tag
                    tagged_references = tag.GetTaggedReferences()
                    if tagged_references:
                        elem_reference = tagged_references[0]
                        leader_end = tag.GetLeaderEnd(elem_reference)
                        elbow_position = XYZ(leader_end.X, new_location.Y, new_location.Z)
                        tag.SetLeaderElbow(elem_reference, elbow_position)

            # Start a transaction to set the Leader Type parameter
            with revit.Transaction("Set Tag Leader Type"):
                # Loop through the selected tags and set the Leader Type parameter to Attached End
                for tag in tags:
                    tag.LeaderEndCondition = LeaderEndCondition.Attached

            # Commit the outer transaction group
            tg_outer.Assimilate()

        forms.alert('Tags aligned', title='Success')
    except Exception as ex:
        # Handle any exceptions by showing an error message
        forms.alert("Error: " + str(ex))

# Run the script if this file is executed as the main program
if __name__ == '__main__':
    arrange_tags_vertically()
