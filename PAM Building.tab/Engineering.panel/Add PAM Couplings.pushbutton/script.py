# -*- coding: utf-8 -*-
__title__ = "Place\nPAM Couplings"
__author__ = "PAM Building UK"
__doc__ = """Version = 1.0
Date    = 01.08.2024
__________________________________________________________________
Compatibility:

Revit 2023+
__________________________________________________________________
Description:

Places PAM couplings every 3m on selected pipes.
__________________________________________________________________
How-to:

-> Click the button
-> Select desired coupling and press 'Select Pipes'
-> Select the pipes and press 'Finish' to complete
__________________________________________________________________
"""

# Import required classes and add references to required libraries
import os
import clr
import webbrowser

# Add references to the necessary assemblies
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')

import System
from System.Windows.Controls import Button
from System.Windows.Input import MouseButtonState

from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException

from pyrevit import revit, forms, script
from pyrevit.forms import WPFWindow

import re  # Import regular expressions module

import Autodesk
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *

clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")
clr.AddReference("RevitNodes")

import Revit
clr.ImportExtensions(Revit.Elements)

# Variables
doc = revit.doc
uidoc = revit.uidoc

output = script.get_output()

# Function to get length of pipes in meters 
def get_pipe_length(pipe):
    length_param = pipe.get_Parameter(BuiltInParameter.CURVE_ELEM_LENGTH)
    if length_param:
        length_in_feet = length_param.AsDouble()
        length_in_meters = UnitUtils.ConvertFromInternalUnits(length_in_feet, UnitTypeId.Meters)
        return length_in_meters
    else:
        pipe_curve = pipe.Location.Curve
        length_in_feet = pipe_curve.Length
        length_in_meters = UnitUtils.ConvertFromInternalUnits(length_in_feet, UnitTypeId.Meters)
        return length_in_meters

# Function to get diameter of pipes in millimeters
def get_pipe_diameter(pipe):
    diameter_param = pipe.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
    if diameter_param:
        diameter_in_feet = diameter_param.AsDouble()
        diameter_in_mm = UnitUtils.ConvertFromInternalUnits(diameter_in_feet, UnitTypeId.Millimeters)
        return diameter_in_mm
    return None

# Function to extract DN size from family type name and validate
def extract_and_validate_dn_size(type_name):
    match = re.search(r'DN(\d+)[xX](\d+)', type_name)
    if match:
        dn1 = int(match.group(1))
        dn2 = int(match.group(2))
        # Ensure both DN numbers are the same to avoid variants like DN100x110
        if dn1 == dn2:
            return dn1
    return None

def compute_intermediate_points(start_point, end_point, interval=3.0, adjustment_threshold=3.1, adjustment_distance=0.1):
    # Calculate the total length of the pipe in feet
    total_length_feet = start_point.DistanceTo(end_point)  # Distance in feet

    # Convert total length to meters
    total_length_meters = total_length_feet * 0.3048  # Conversion factor from feet to meters

    # Normalize direction vector
    direction_vector = (end_point - start_point).Normalize()

    # Generate intermediate points every `interval` meters
    points = []
    current_distance = interval

    while current_distance < total_length_meters:
        point = start_point + direction_vector * (current_distance / 0.3048)  # Convert distance to feet
        points.append(point)
        current_distance += interval

    # Check the length of the last segment
    remaining_distance = total_length_meters - (len(points) * interval)

    if 3.0 < remaining_distance < adjustment_threshold:
        if points:
            # Adjust the last point by moving it closer to the start point
            points[-1] = start_point + direction_vector * ((len(points) * interval - adjustment_distance) / 0.3048)  # Convert adjustment to feet

    return points

# Lists to store pipes that meet the criteria (OK for coupling)
ok_pipes = []
not_ok_pipes = []

def show_window():
    """Load and display the WPF window for user interaction."""
    # Path to your XAML file relative to the script directory
    script_dir = os.path.dirname(__file__)
    xaml_file_path = os.path.join(script_dir, 'UI.xaml')

    # Load the WPF window from the XAML file
    window = WPFWindow(xaml_file_path)

    selected_coupling = [None]  # To store the selected coupling type

    def close_button_click(sender, args):
        """Handle the close button click event."""
        window.Close()

    def run_button_click(sender, args):
        """Handle the Place Couplings button click event."""
        # Check which radio button is selected
        if window.EC002.IsChecked:
            selected_coupling[0] = "EC002 - Ductile Iron Coupling"
        elif window.EC002NG.IsChecked:
            selected_coupling[0] = "EC002NG - RAPID S NG Coupling"
        elif window.EC002HP.IsChecked:
            selected_coupling[0] = "EC002HP - HP Flex Coupling"
        elif window.EC002HP_G.IsChecked:
            selected_coupling[0] = "EC002HP-G - HP Grip Coupling"

        if selected_coupling[0]:
            # Close the window and return the selected coupling
            window.DialogResult = True
            window.Close()
        else:
            forms.alert('Please select a coupling type.', title='Select Coupling')

    def on_image_click(sender, event_args):
        """Handle the image click event to open a URL."""
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
    logo_image = window.FindName('logo')
    if logo_image:
        logo_image.MouseLeftButtonDown += on_image_click

    # Find the TitleBar and attach the drag event handler
    title_bar = window.FindName('TitleBar')
    if title_bar:
        title_bar.MouseLeftButtonDown += header_drag

    # Show the window
    window.ShowDialog()

    # Retrieve and return selected coupling
    if window.DialogResult:
        return selected_coupling[0]
    else:
        return None

# Show the custom window and get the selected coupling type
selected_coupling = show_window()

if not selected_coupling:
    script.exit()

# Define allowed diameters and keywords based on coupling type
if selected_coupling == 'EC002 - Ductile Iron Coupling':
    allowed_diameters = [50, 70, 100, 125, 150, 200, 250, 300]
    keywords = ['Ductile Iron Coupling']
elif selected_coupling == 'EC002NG - RAPID S NG Coupling':
    allowed_diameters = [50, 70, 100, 125, 150, 200, 250, 300]
    keywords = ['NG Coupling']
elif selected_coupling == 'EC002HP - HP Flex Coupling':
    allowed_diameters = [50, 70, 100, 125, 150, 200, 250, 300, 400, 500, 600]
    keywords = ['Flex Coupling']
elif selected_coupling == 'EC002HP-G - HP Grip Coupling':
    allowed_diameters = [50, 70, 100, 125, 150, 200, 250, 300, 400, 500, 600]
    keywords = ['Grip Coupling']

# Convert allowed diameters to integers
allowed_diameters = [int(diameter) for diameter in allowed_diameters]

# Collect matching families and filter out DN sizes with invalid formats
matching_families = []
collector = FilteredElementCollector(doc).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_PipeFitting)

for family_symbol in collector:
    description_param = family_symbol.get_Parameter(BuiltInParameter.ALL_MODEL_DESCRIPTION)
    if description_param:
        description_value = description_param.AsString()
        if description_value and any(keyword in description_value for keyword in keywords):
            family_name = family_symbol.FamilyName
            family_type_name = family_symbol.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM).AsString()

            # Extract and validate DN size from family type name
            dn_size = extract_and_validate_dn_size(family_type_name)

            # Exclude DN sizes that are not allowed
            if dn_size and dn_size in allowed_diameters:
                matching_families.append((dn_size, family_symbol))

# Sort matching families based on DN size (smallest to largest)
matching_families.sort(key=lambda x: x[0])

# Extract sorted family symbols for output
sorted_matching_families = [fam[1] for fam in matching_families]

# Function to check if the selected coupling type has a suitable family loaded in Revit
def check_coupling_compatibility():
    return len(matching_families) > 0

# Check compatibility of couplings
if not check_coupling_compatibility():
    forms.alert(
        "No suitable family found in your project for selected '{}'.".format(selected_coupling),
        title='Load PAM Building Content'
    )

else:
    while True: # Loop to keep the selection filter active
        try:
            # Define a selection filter to allow the user to select only pipes
            class CategorySelectionFilter(ISelectionFilter):
                def __init__(self, category_names):
                    self.category_names = category_names

                def AllowElement(self, e):
                    return e.Category.Name in self.category_names

                def AllowReference(self, ref, point):
                    return True

            with forms.WarningBar(title="Select pipes and press Finish when complete"):
                collector = uidoc.Selection.PickObjects(ObjectType.Element, CategorySelectionFilter(["Pipes"]), 'Select Pipes')

            if collector is None or len(collector) == 0:  # No pipes selected or operation canceled
                forms.alert('No pipes have been selected', title='Select Pipes')
                continue
            else:
                # Flags to track alert conditions
                found_suitable_pipe = False
                found_unsuitable_pipe = False

                # Process selected pipes and categorize them
                for ref in collector:
                    pipe = doc.GetElement(ref.ElementId)
                    pipe_length = get_pipe_length(pipe)
                    pipe_diameter = get_pipe_diameter(pipe)

                    if pipe_length > 3.01:
                        if pipe_diameter and int(pipe_diameter) in allowed_diameters:
                            ok_pipes.append(pipe)
                            found_suitable_pipe = True
                        else:
                            not_ok_pipes.append(pipe)
                            found_unsuitable_pipe = True
                    else:
                        # Pipes less than 3.01 meters are not considered for coupling
                        # but we need to track if all pipes are less than 3m
                        found_unsuitable_pipe = True

                # Check conditions to show the alert
                if not found_suitable_pipe and found_unsuitable_pipe:
                    forms.alert(
                        "Unable to place {} on selected pipes".format(selected_coupling),
                        title='Check Pipe Diameter and Length'
                    )

                # Continue with the rest of the script
                if ok_pipes:
                    output.print_md("### {} successfully placed on the following pipes:".format(selected_coupling))
                    for pipe in ok_pipes:
                        pipe_length = get_pipe_length(pipe)
                        pipe_diameter = get_pipe_diameter(pipe)
                        type_name = pipe.get_Parameter(BuiltInParameter.ELEM_TYPE_PARAM).AsValueString()

                        output.print_md(
                            "- Pipe {} Length: {:.2f} m, Diameter: {:.2f} mm, Type: {}".format(
                                output.linkify(pipe.Id), pipe_length, pipe_diameter, type_name))

                    # Initialize a counter for total intermediate points
                    total_intermediate_points = 0

                    # Analyze pipes to find start and end points and generate intermediate points
                    for pipe in ok_pipes:
                        pipe_curve = pipe.Location.Curve
                        start_point = pipe_curve.GetEndPoint(0)
                        end_point = pipe_curve.GetEndPoint(1)

                        # Compute intermediate points every 3 meters
                        intermediate_points = compute_intermediate_points(start_point, end_point, interval=3.0)

                        # Update the total number of intermediate points
                        total_intermediate_points += len(intermediate_points)

                    if total_intermediate_points > 1:
                        # Output total number of intermediate points
                        output.print_md(
                            "###Congratulations! You successfully placed {} couplings!".format(
                                total_intermediate_points))
                    elif total_intermediate_points==1:
                        # Output total number of intermediate points
                        output.print_md(
                            "###Congratulations! You successfully placed {} coupling!".format(
                                total_intermediate_points))
                    else:
                        # Output total number of intermediate points
                        output.print_md(
                            "No {} was placed ".format(
                                selected_coupling))
                    # Get unique pipe types from ok_pipes
                    unique_pipe_types = {}
                    for pipe in ok_pipes:
                        type_name = pipe.get_Parameter(BuiltInParameter.ELEM_TYPE_PARAM).AsValueString()
                        if type_name not in unique_pipe_types:
                            unique_pipe_types[type_name] = pipe

                    unique_elements = list(unique_pipe_types.values())

                    # Reverse the sorted_matching_families list
                    reversed_matching_families = sorted_matching_families[::-1]

                    # Begin a transaction group
                    with TransactionGroup(doc, "Add PAM Couplings") as group:
                        group.Start()

                        # Transaction to add rules to routing preferences
                        with Transaction(doc, "Add coupling types to Routing Preferences") as t1:
                            t1.Start()

                            try:
                                # Track the number of rules added
                                num_rules_added = len(reversed_matching_families)  # Count of reversed_matching_families

                                for element in unique_elements:
                                    elemType = doc.GetElement(element.GetTypeId())
                                    routManager = elemType.RoutingPreferenceManager

                                    for fam in reversed_matching_families:
                                        newRule = RoutingPreferenceRule(fam.Id, "Coupling Rule")

                                        # Get family type name
                                        type_name = fam.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM).AsString()

                                        # Extract and validate DN size from family type name
                                        dn_size = extract_and_validate_dn_size(type_name)

                                        if dn_size is not None:
                                            # Use dn_size directly as System.Double
                                            min_size = System.Double(dn_size / 304.8)
                                            max_size = System.Double(dn_size / 304.8)
                                            primary_size_criterion = PrimarySizeCriterion(min_size, max_size)
                                        else:
                                            # Default size if DN size is invalid
                                            min_size = System.Double(100/304.8)
                                            max_size = System.Double(100/304.8)
                                            primary_size_criterion = PrimarySizeCriterion(min_size, max_size)

                                        # Apply criteria directly to the rule
                                        newRule.AddCriterion(primary_size_criterion)

                                        # Add the rule to the routing preferences manager
                                        routManager.AddRule(RoutingPreferenceRuleGroupType.Unions, newRule, 0)

                                t1.Commit()

                            except Exception as e:
                                t1.RollBack()
                                output.print_md("Error while adding rules: {}".format(e))
                                group.RollBack()
                                raise

                        # Transaction to split pipes
                        with Transaction(doc, "Split pipes") as t2:
                            t2.Start()

                            try:
                                parents, childs, fittings = [], [], []
                                children = {}

                                for pipe in ok_pipes:
                                    pipe_curve = pipe.Location.Curve
                                    start_point = pipe_curve.GetEndPoint(0)
                                    end_point = pipe_curve.GetEndPoint(1)

                                    intermediate_points = compute_intermediate_points(start_point, end_point,
                                                                                        interval=3.0)

                                    for p in intermediate_points:
                                        to_check = [pipe]
                                        if pipe.Id in children:
                                            to_check.extend(children[pipe.Id])

                                        splitId = None
                                        for ec in to_check:
                                            if isinstance(ec, Autodesk.Revit.DB.Plumbing.Pipe):
                                                try:
                                                    splitId = Autodesk.Revit.DB.Plumbing.PlumbingUtils.BreakCurve(doc,
                                                                                                                    ec.Id,
                                                                                                                    p)
                                                    break
                                                except:
                                                    pass
                                        if splitId:
                                            split = doc.GetElement(splitId)
                                            if hasattr(split, "ConnectorManager"):
                                                newPipeConnectors = split.ConnectorManager.Connectors
                                                connA = None
                                                connB = None
                                                for c in ec.ConnectorManager.Connectors:
                                                    pc = c.Origin
                                                    nearest = [x for x in newPipeConnectors if
                                                                pc.DistanceTo(x.Origin) < 0.01]
                                                    if nearest:
                                                        connA = c
                                                        connB = nearest[0]
                                                try:
                                                    fittings.append(doc.Create.NewUnionFitting(connA, connB))
                                                except:
                                                    pass

                                            if pipe.Id in children:
                                                children[pipe.Id].append(split)
                                            else:
                                                children[pipe.Id] = [split]
                                            parents.append(ec)
                                            childs.append(split)
                                        else:
                                            parents.append(None)
                                            childs.append(None)

                                t2.Commit()

                            except Exception as ex:
                                t2.RollBack()
                                output.print_md("Error while splitting pipes: {}".format(ex))
                                group.RollBack()
                                raise

                        # Transaction to remove the rules added in t1
                        with Transaction(doc, "Remove coupling rules") as t3:
                            t3.Start()
                            try:
                                num_rules_to_remove = len(reversed_matching_families)  # Number of rules to remove

                                for element in unique_elements:
                                    elemType = doc.GetElement(element.GetTypeId())
                                    routManager = elemType.RoutingPreferenceManager

                                    # Remove rules starting from index 0, one at a time
                                    for _ in range(num_rules_to_remove):
                                        routManager.RemoveRule(RoutingPreferenceRuleGroupType.Unions, 0)

                                t3.Commit()

                            except Exception as ex:
                                t3.RollBack()
                                output.print_md("Error while removing rules: {}".format(ex))
                                group.RollBack()
                                raise

                        # Commit the transaction group
                        group.Assimilate()

                    # Output pipes that do not meet the diameter criteria (Unable to place coupling)
                    if not_ok_pipes:
                        output.print_md("### Unable to place {} on the following pipes:".format(selected_coupling))
                        for pipe in not_ok_pipes:
                            pipe_length = get_pipe_length(pipe)
                            pipe_diameter = get_pipe_diameter(pipe)
                            type_name = pipe.get_Parameter(BuiltInParameter.ELEM_TYPE_PARAM).AsValueString()

                            output.print_md(
                                "- Pipe {} Length: {:.2f} m, Diameter: {:.2f} mm, Type: {}".format(
                                    output.linkify(pipe.Id), pipe_length, pipe_diameter, type_name))

        except OperationCanceledException:
            forms.alert('User cancelled selection', title='Select Pipes')
        break
