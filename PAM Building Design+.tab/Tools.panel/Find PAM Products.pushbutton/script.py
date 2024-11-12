# -*- coding: utf-8 -*-
__title__ = "Isolate PAM Products"

# Import required classes and add references to required libraries
import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
clr.AddReference("System")

from Autodesk.Revit.DB import MEPCurve, BuiltInParameter, FilteredElementCollector, FamilyInstance, ElementId, BuiltInCategory, ElementType, View
from System.Collections.Generic import List

from pyrevit import revit, forms

# Variables
uidoc = revit.uidoc
doc = revit.doc

# Initialize an empty list to store family instances and pipes with the desired Manufacturer
matching_elements = []

# Collect all family instances in the project
family_instances = FilteredElementCollector(doc).OfClass(FamilyInstance).ToElements()

# Iterate through each family instance to check the Manufacturer parameter
for instance in family_instances:
    family_symbol = instance.Symbol
    manufacturer_param = family_symbol.get_Parameter(BuiltInParameter.ALL_MODEL_MANUFACTURER)
    if manufacturer_param:
        manufacturer_value = manufacturer_param.AsString()
        if manufacturer_value and 'PAM Building' in manufacturer_value:
            matching_elements.append(instance)

# Collect all pipe types by filtering for types within the PipeCurves category
pipe_type_ids = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_PipeCurves).WhereElementIsElementType().ToElementIds()
pipe_types = [doc.GetElement(id) for id in pipe_type_ids]

# Iterate through each Pipe Type to check the Manufacturer parameter
for pipe_type in pipe_types:
    if isinstance(pipe_type, ElementType):  # Ensure we're dealing with a pipe type
        manufacturer_param = pipe_type.get_Parameter(BuiltInParameter.ALL_MODEL_MANUFACTURER)
        if manufacturer_param:
            manufacturer_value = manufacturer_param.AsString()
            if manufacturer_value and 'PAM Building' in manufacturer_value:
                # Find all pipe instances of this type
                pipe_instances = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_PipeCurves).WhereElementIsNotElementType().ToElements()
                for pipe in pipe_instances:
                    if isinstance(pipe, MEPCurve) and pipe.GetTypeId() == pipe_type.Id:
                        matching_elements.append(pipe)

# Check if any elements matched
if matching_elements:
    element_ids = List[ElementId]([element.Id for element in matching_elements])
    # uidoc.Selection.SetElementIds(element_ids)

    # Isolate elements temporarily
    view = uidoc.ActiveView
    with revit.Transaction(__title__):
        view.IsolateElementsTemporary(element_ids)
else:
    # Show an alert if no matching elements were found
    forms.alert("No PAM Building products in this view.", title="No Products Found", warn_icon=True)
