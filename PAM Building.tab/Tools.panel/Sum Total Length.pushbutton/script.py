# -*- coding: utf-8 -*-
__title__ = "Sum Total Pipe Length"

# Import required classes and add references to required libraries
import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.UI.Selection import ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.UI.Selection import ISelectionFilter
from Autodesk.Revit.DB import BuiltInParameter

from pyrevit import revit, forms

# Variables
uidoc = revit.uidoc
doc = revit.doc

# Define a selection filter to allow the user to select only pipes
class SelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        return element.Category and element.Category.Name == "Pipes"

    def AllowReference(self, reference, position):
        return False

# Function to get length of pipes in meters
def get_pipe_length(pipe):
    length_param = pipe.get_Parameter(BuiltInParameter.CURVE_ELEM_LENGTH)
    if length_param:
        length_in_feet = length_param.AsDouble()
        length_in_meters = length_in_feet * 0.3048
        return length_in_meters
    else:
        pipe_curve = pipe.Location.Curve
        length_in_feet = pipe_curve.Length
        length_in_meters = length_in_feet * 0.3048
        return length_in_meters

def select_pipework():
    while True:  # Loop to keep the selection filter active
        try:
            with forms.WarningBar(title='Select pipes and press Finish when complete'):
                # Create an instance of SelectionFilter
                filter = SelectionFilter()

                # Prompt user to select elements
                selected_ids = uidoc.Selection.PickObjects(ObjectType.Element, filter)
                if not selected_ids:
                    forms.alert('No pipes have been selected', title='Select Pipes')
                    continue

                # Return the selected elements
                return [doc.GetElement(id.ElementId) for id in selected_ids]

        except OperationCanceledException:
            forms.alert('User cancelled selection', title='Select Pipes')
            return None
        except Exception as ex:
            forms.alert("Error: " + str(ex))
            return None

try:
    # Call the select_pipework function to get the selected pipework
    selected_elements = select_pipework()

    if selected_elements:
        total_length = 0
        for pipe in selected_elements:
            total_length += get_pipe_length(pipe)

        forms.alert('Total length of selected pipes: {:.2f} m'.format(total_length), title='Success')

except Exception as ex:
    # Handle any other exceptions by showing an error message
    forms.alert("Error: " + str(ex))
