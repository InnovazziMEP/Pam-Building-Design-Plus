# -*- coding: utf-8 -*-
__title__ = "Rotate\nAccess Doors"

#Add imports
import os
import math
import clr
import webbrowser

# Add references to the necessary assemblies
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')

from System.Windows.Controls import Button, TextBox, Image
from System.Windows.Input import MouseButtonState

from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException

from pyrevit import revit, forms, DB
from pyrevit.forms import WPFWindow

# Variables
uidoc = revit.uidoc
doc = revit.doc

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> SELECTION FILTER
class SelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        return element.Category and element.Category.Name == "Pipe Fittings"

    def AllowReference(self, reference, position):
        return False

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> FUNCTIONS
def select_elements():
    while True: # Loop to keep the selection filter active
        try:
            with forms.WarningBar(title='Select access doors and press Finish when complete'):
                # Create an instance of SelectionFilter
                filter = SelectionFilter()

                # Prompt user to select elements
                selected_ids = uidoc.Selection.PickObjects(ObjectType.Element, filter, 'Select Access Doors')
                selected_elements = [doc.GetElement(id.ElementId) for id in selected_ids]

            if not selected_ids:  # No pipe fittings selected or operation cancelled
                forms.alert('No access doors have been selected', title='Select Access Doors')
                continue
            else:
                # Pass the selected elements to the window
                show_window(selected_elements)

        except OperationCanceledException:
            forms.alert('User cancelled selection', title='Select Access Doors')
        break

def rotate_element(elem, degrees_to_rotate):
    # Get center point
    origin = elem.Location.Point

    # Create axis line
    axis_line = DB.Line.CreateBound(origin, origin + DB.XYZ.BasisZ)

    # Rotate element
    DB.ElementTransformUtils.RotateElement(doc, elem.Id, axis_line, math.radians(float(degrees_to_rotate)))
    
def show_window(selected_elements):
    # Path to your XAML file relative to the script directory
    script_dir = os.path.dirname(__file__)
    xaml_file_path = os.path.join(script_dir, 'UI.xaml')

    # Load the WPF window from the XAML file
    window = WPFWindow(xaml_file_path)

    # Access controls directly using their names
    def close_button_click(sender, args):
        window.Close()

    def run_button_click(sender, args):
        input_degrees = window.FindName('input_degrees')
        if input_degrees and isinstance(input_degrees, TextBox):
            degrees_text = input_degrees.Text
            try:
                degrees = float(degrees_text)
            except ValueError:
                forms.alert('Please enter a numeric value', title='Invalid Input')
                return

            total_rotated_elements = 0  # Initialize counter for rotated elements

            with DB.Transaction(doc, __title__) as t:
                t.Start()
                for element in selected_elements:
                    try:
                        rotate_element(element, -degrees)
                        total_rotated_elements += 1  # Increment counter for each successful rotation
                    except Exception as ex:
                        forms.alert("Could not rotate access door - {}. Error: {}".format(element.Id, ex))
                t.Commit()

            window.Close()
            
            # Determine the message based on the number of rotated elements
            if total_rotated_elements > 0:
                if total_rotated_elements == 1:
                    message = "You rotated 1 access door!"
                else:
                    message = "You rotated {} access doors!".format(total_rotated_elements)
                forms.alert(message, title='Success')
            else:
                forms.alert("You haven't rotated any access doors", title='Info')


    def on_image_click(sender, event_args):
        url = "https://www.pambuilding.co.uk/"
        webbrowser.open(url)

    def header_drag(sender, event_args):
        """Allow dragging the window by the header."""
        if event_args.LeftButton == MouseButtonState.Pressed:
            window.DragMove()

    # Attach event handlers
    close_button = window.FindName('button_close')
    if close_button and isinstance(close_button, Button):
        close_button.Click += close_button_click

    run_button = window.FindName('button_run')
    if run_button and isinstance(run_button, Button):
        run_button.Click += run_button_click

    # Attach the image click event handler
    image = window.FindName('logo')
    if image and isinstance(image, Image):
        image.MouseLeftButtonDown += on_image_click

    # Find the TitleBar and attach the drag event handler
    title_bar = window.FindName('TitleBar')
    if title_bar:
        title_bar.MouseLeftButtonDown += header_drag

    # Show the window
    window.ShowDialog()

# Start the selection process and then show the window
select_elements()
