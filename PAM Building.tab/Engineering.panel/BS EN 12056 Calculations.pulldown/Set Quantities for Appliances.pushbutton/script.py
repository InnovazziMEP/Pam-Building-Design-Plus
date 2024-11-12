# -*- coding: utf-8 -*-
__title__ = "Set Foul Drainage Appliances"

# Add imports
import os
import clr
import webbrowser

# If failed, add references to the necessary assemblies and try again
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')

#import System
from System.Windows.Controls import Button, TextBox, Image
from System.Windows.Input import MouseButtonState

from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException

from pyrevit import revit, forms, DB
from pyrevit.forms import WPFWindow

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> VARIABLES
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
            with forms.WarningBar(title='Select sizing connections and press Finish when complete'):
                # Create an instance of SelectionFilter
                filter = SelectionFilter()

                # Prompt user to select elements
                selected_ids = uidoc.Selection.PickObjects(ObjectType.Element, filter, 'Select Foul Drainage Sizing Connections')
                selected_elements = [doc.GetElement(id.ElementId) for id in selected_ids]

            if not selected_ids:  # No pipe fittings selected or operation cancelled
                forms.alert('No elements have been selected', title='Select Sizing Connections')
                continue
            else:
                # Pass the selected elements to the window
                show_window(selected_elements)

        except OperationCanceledException:
            forms.alert('User cancelled selection', title='Select Sizing Connections')
        break

def show_window(selected_elements):
    # Path to your XAML file relative to the script directory
    script_dir = os.path.dirname(__file__)
    xaml_file_path = os.path.join(script_dir, 'UI.xaml')

    # Load the WPF window from the XAML file
    window = WPFWindow(xaml_file_path)

    def close_button_click(sender, args):
        window.Close()

    def run_button_click(sender, args):
        # List of TextBox names and corresponding parameter names
        text_boxes = {
            'Washbasin': 'Wash Basin',
            'Bidet': 'Bidet',
            'ShowerWithoutPlug': 'Shower Without Plug',
            'ShowerWithPlug': 'Shower With Plug',
            'SingleUrinalWithCistern': 'Single Urinal With Cistern',
            'SlabUrinal': 'Slab Urinal',
            'Bath': 'Bath',
            'KitchenSink': 'Kitchen Sink',
            'Dishwasher': 'Dishwasher (Household)',
            'WashingMachineUpTo6kg': 'Washing Machine Up To 6 kg',
            'WashingMachineUpTo12kg': 'Washing Machine Up To 12 kg',
            'WCWith6lCistern': 'WC With 6 l Cistern',
            'WCWith7_5lCistern': 'WC With 7.5 l Cistern',
            'WCWith9lCistern': 'WC With 9 l Cistern'
        }

        # Dictionary to hold the values from each TextBox
        text_box_values = {}

        for name, param_name in text_boxes.items():
            text_box = window.FindName(name)
            if text_box and isinstance(text_box, TextBox):
                text_box_value = text_box.Text
                try:
                    # Convert value to integer
                    int_value = int(float(text_box_value))
                    text_box_values[param_name] = int_value
                except ValueError:
                    forms.alert('Please enter a valid numeric value for {}'.format(param_name), title='Invalid Input')
                    return

        # Separate elements into suitable and unsuitable
        suitable_elements = []
        unsuitable_count = 0

        for element in selected_elements:
            all_params_present = True
            for param_name in text_boxes.values():
                param = element.LookupParameter(param_name)
                if not param:
                    all_params_present = False
                    break
            if all_params_present:
                suitable_elements.append(element)
            else:
                unsuitable_count += 1

        # Alert if any elements are unsuitable
        if unsuitable_count > 0:
            forms.alert('Some of the selected elements have missing parameters', title='Unsuitable Elements')

        # Write parameters to the suitable elements
        if suitable_elements:
            with DB.Transaction(doc, __title__) as t:
                t.Start()
                for element in suitable_elements:
                    try:
                        # Set parameters for the element
                        for param_name, value in text_box_values.items():
                            param = element.LookupParameter(param_name)
                            if param:
                                if param.StorageType == DB.StorageType.Integer:
                                    param.Set(value)
                                else:
                                    forms.alert("Unsupported parameter type for: {}".format(param_name), title='Unsupported Parameter Type')
                                    return
                    except Exception as ex:
                        forms.alert("Could not set parameters for element - {}. Error: {}".format(element.Id, ex))
                t.Commit()

        # Close the UI before asking the user if they want to continue
        window.Close()

        # Determine the message based on the number of suitable elements
        total_suitable_elements = len(suitable_elements)
        if total_suitable_elements > 0:
            if total_suitable_elements == 1:
                message = "You updated 1 element!"
            else:
                message = "You updated {} elements!".format(total_suitable_elements)
            forms.alert(message, title='Success')
        else:
            forms.alert("You haven't updated any elements", title='Info')

        # Ask the user if they want to continue with another selection
        continue_selection = forms.alert("Do you want to select more elements and set appliances?", title="Continue?", yes=True, no=True)
        if continue_selection:  # If the user selects 'Yes'
            # Restart the main function to allow for another selection
            main()

    def on_image_click(sender, event_args):
        url = "https://www.pambuilding.co.uk"
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

def main():
    selected_elements = select_elements()
    if selected_elements:
        show_window(selected_elements)

# Return the main function
main()
