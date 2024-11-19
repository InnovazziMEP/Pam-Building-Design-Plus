# -*- coding: utf-8 -*-
__title__ = "Set Reference Level"

# Import required classes and add references to required libraries
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

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.Exceptions import OperationCanceledException

# Variables
doc = revit.doc
uidoc = revit.uidoc

# Define the list of built-in categories
required_categories = [
    "Air Terminals", "Audio Visual Devices", "Cable Tray Fittings", "Cable Trays", 
    "Communication Devices", "Conduit Fittings", "Conduits", "Data Devices", 
    "Duct Accessories", "Duct Fittings", "Ducts", "Electrical Equipment", 
    "Electrical Fixtures", "Fire Alarm Devices", "Fire Protection", "Flex Ducts", 
    "Flex Pipes", "Food Service Equipment", "Lighting Devices", "Lighting Fixtures", 
    "Mechanical Control Devices", "Mechanical Equipment", "Medical Equipment", 
    "Nurse Call Devices", "Pipe Accessories", "Pipe Fittings", "Pipes", 
    "Plumbing Equipment", "Plumbing Fixtures", "Security Devices", "Sprinklers", 
    "Telephone Devices"
]

def convert_to_millimeters(feet_value):
    """Convert feet to millimeters."""
    return UnitUtils.Convert(feet_value, UnitTypeId.Feet, UnitTypeId.Millimeters)

# Custom class to represent a category item in the ListBox
class CategoryItem:
    """Class to represent a category item in the ListBox."""
    def __init__(self, category):
        self.Category = category
        self.IsChecked = False
        self.Name = category.Name

# Collect categories and create a list of CategoryItem objects
category_items = {}
categories = doc.Settings.Categories

for category in categories:
    if isinstance(category, Category):
        category_key = category.Name
        if category_key in required_categories and category_key not in category_items:
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

def get_sorted_levels(doc):
    levels = FilteredElementCollector(doc).OfClass(Level).ToElements()
    return sorted(levels, key=lambda lvl: lvl.ProjectElevation)

def create_planes_at_levels(doc):
    """Create planes at each level"""
    sorted_levels = list(reversed(get_sorted_levels(doc)))
    
    # Define a list to hold the created planes
    planes = []

    for level in sorted_levels:
        # Create a point at the elevation level (in feet)
        point = XYZ(0, 0, level.ProjectElevation)
        
        # Create a plane at the level's elevation
        plane = Plane.CreateByNormalAndOrigin(XYZ.BasisZ, point)
        planes.append((plane, level))
    
    return planes

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

# Define built-in parameters
LEVEL_PARAM = BuiltInParameter.FAMILY_LEVEL_PARAM
ELEVATION_PARAM = BuiltInParameter.INSTANCE_ELEVATION_PARAM
REFERENCE_LEVEL_PARAM = BuiltInParameter.RBS_START_LEVEL_PARAM

#This definition is used for elements with 'Level' and 'Elevation from Level' parameters
def identify_level_and_elevation_from_level ():
    # Retrieve the planes at levels and reverse them to get the closest level first
    planes_at_levels = create_planes_at_levels(doc)
    sorted_levels = list(reversed(get_sorted_levels(doc)))

    if not planes_at_levels:
        print("No planes were created for levels.")
        return []

    if not sorted_levels:
        print("No levels found in the project.")
        return []

    # Identify the lowest level
    lowest_level = sorted_levels[-1]  # After reversing, the last item is the lowest level

    # Define the 5mm offset as feet
    offset_mm = 5.0
    offset_ft = UnitUtils.Convert(offset_mm, UnitTypeId.Millimeters, UnitTypeId.Feet)

    # List to store results
    results = []

    # Iterate over level_and_elevation_elements
    for element_data in level_and_elevation_elements:
        element_id = element_data['Element ID']

        # Retrieve the element and its location
        element = doc.GetElement(element_id)

        if isinstance(element, FamilyInstance):
            # Get the center point of the family instance
            location = element.Location
            center_point = location.Point 
            
            # Flag to check if the element intersects with any level
            intersects_with_level = False

            # Check intersection with each plane
            for plane, level in planes_at_levels:
                # Define the direction as -Z axis
                direction = XYZ(0, 0, -1)

                # Create a line from an offset point above the center of the family instance downward
                line_start = center_point + XYZ(0, 0, offset_ft)  # Start point 5mm above
                line_end = center_point + XYZ(0, 0, offset_ft - 10000)  # Extend line far enough to ensure intersection
                
                # Define plane parameters
                plane_normal = plane.Normal
                plane_point = plane.Origin
                
                # Compute the direction vector of the line
                line_vector = line_end - line_start

                # Calculate the dot product of the plane normal and the line direction
                denom = plane_normal.DotProduct(line_vector)
                
                # Avoid division by zero; if denom is close to zero, line is parallel to plane
                if abs(denom) < 1e-6:
                    continue
                
                # Calculate the parameter t for the intersection point
                t = (plane_point - line_start).DotProduct(plane_normal) / denom

                # Calculate the intersection point
                intersection_point = line_start + t * line_vector

                # Check if the intersection point is within the line segment
                if min(line_start.X, line_end.X) <= intersection_point.X <= max(line_start.X, line_end.X) and \
                   min(line_start.Y, line_end.Y) <= intersection_point.Y <= max(line_start.Y, line_end.Y) and \
                   min(line_start.Z, line_end.Z) <= intersection_point.Z <= max(line_start.Z, line_end.Z):
                    # Calculate the distance between the center point and the intersection point
                    distance = intersection_point.DistanceTo(center_point)                   
                    
                    # Store the result
                    results.append({
                        'Element ID': element_id,
                        'Level': level,
                        'Elevation from Level': distance
                    })
                    intersects_with_level = True
                    break  # Exit after finding the first intersection

            # If no intersection was found, calculate the distance to the lowest level
            if not intersects_with_level:
                # Calculate the distance between the element and the lowest level
                z_distance = center_point.Z - lowest_level.Elevation

                # Store the result
                results.append({
                    'Element ID': element_id,
                    'Level': lowest_level,
                    'Elevation from Level': z_distance
                })

    return results

def GetElementCurves(element):
    """Retrieve the geometry curves of a given element using Location Curve."""
    curves = []
    
    # Check if the element has a location and if it's represented by a curve
    if hasattr(element.Location, "Curve"):
        curve = element.Location.Curve
        curves.append(curve)
    
    return curves

def IntersectionCurveAndPlane(plane, curve):
    """Check if a line curve intersects with a plane and return the intersection point."""
    if isinstance(curve, Line):
        return _intersect_line_with_plane(plane, curve)
    else:
        print("Only line curves are supported.")
        return None

def _intersect_line_with_plane(plane, line):
    """Check intersection between a plane and a line."""
    # Get the plane parameters
    plane_point = plane.Origin
    plane_normal = plane.Normal

    # Get the line start and end points
    line_start = line.GetEndPoint(0)
    line_end = line.GetEndPoint(1)

    # Define the line direction
    line_direction = line_end - line_start

    # Check if the line is parallel to the plane
    denom = plane_normal.DotProduct(line_direction)
    if abs(denom) < 1e-6:
        # Line is parallel to the plane
        return None

    # Calculate the parameter t for the intersection point
    t = (plane_point - line_start).DotProduct(plane_normal) / denom

    if t < 0 or t > 1:
        # Intersection point is not on the line segment
        return None

    # Calculate the intersection point
    intersection_point = line_start + t * line_direction

    return intersection_point

#This definition is used for elements with 'Reference Level' parameter, i.e. Pipes, Ducts, Cable Trays etc.
def identify_reference_level():
    """Analyze elements with reference levels by retrieving their curves, checking their intersections with level planes, and printing the details."""
    
    # Retrieve the planes at levels
    planes_at_levels = create_planes_at_levels(doc)
    sorted_levels = list(reversed(get_sorted_levels(doc)))

    if not planes_at_levels:
        print("No planes were created for levels.")
        return []

    if not sorted_levels:
        print("No levels found in the project.")
        return []

    # List to store results
    results = []

    # Iterate over reference_level_elements
    for element_data in reference_level_elements:
        element_id = element_data['Element ID']

        # Retrieve the element
        element = doc.GetElement(element_id)

        # Get the curves of the element using Location.Curve
        curves = GetElementCurves(element)

        if curves:
            for curve in curves:
                start_point = curve.GetEndPoint(0)
                end_point = curve.GetEndPoint(1)

                # Store curve details
                curve_info = {
                    'Element ID': element_id,
                }
                results.append(curve_info)
                
                # Check intersections with all level planes
                intersections = []
                for plane, level in planes_at_levels:
                    intersection = IntersectionCurveAndPlane(plane, curve)
                    if intersection:
                        # Convert intersection point to millimeters for output
                        intersection_mm = XYZ(
                            convert_to_millimeters(intersection.X),
                            convert_to_millimeters(intersection.Y),
                            convert_to_millimeters(intersection.Z)
                        )
                        intersections.append((level, intersection_mm))
                
                # Determine if we have more than 0 intersections
                if len(intersections) > 0:
                    # Use top point
                    top_point = end_point if end_point.Z > start_point.Z else start_point
                    line_start = top_point
                else:
                    # Use center point
                    center_point = XYZ(
                        (start_point.X + end_point.X) / 2,
                        (start_point.Y + end_point.Y) / 2,
                        (start_point.Z + end_point.Z) / 2
                    )
                    line_start = center_point

                # Define the line end point far below to ensure intersection
                line_end = line_start + XYZ(0, 0, -10000)

                # Check intersection with each plane
                found_intersection = False
                for plane, level in planes_at_levels:
                    plane_normal = plane.Normal
                    plane_point = plane.Origin

                    # Compute the direction vector of the line
                    line_vector = line_end - line_start

                    # Calculate the dot product of the plane normal and the line direction
                    denom = plane_normal.DotProduct(line_vector)
                    
                    # Avoid division by zero; if denom is close to zero, line is parallel to plane
                    if abs(denom) < 1e-6:
                        continue
                    
                    # Calculate the parameter t for the intersection point
                    t = (plane_point - line_start).DotProduct(plane_normal) / denom

                    # Calculate the intersection point
                    intersection_point = line_start + t * line_vector

                    # Check if the intersection point is within the line segment
                    if min(line_start.X, line_end.X) <= intersection_point.X <= max(line_start.X, line_end.X) and \
                       min(line_start.Y, line_end.Y) <= intersection_point.Y <= max(line_start.Y, line_end.Y) and \
                       min(line_start.Z, line_end.Z) <= intersection_point.Z <= max(line_start.Z, line_end.Z):
                        # Convert intersection point to millimeters
                        intersection_mm = XYZ(
                            convert_to_millimeters(intersection_point.X),
                            convert_to_millimeters(intersection_point.Y),
                            convert_to_millimeters(intersection_point.Z)
                        )
                        results.append({
                            'Element ID': element_id,
                            'Reference Level': level,
                        })
                        found_intersection = True
                        break  # Exit after finding the first intersection

                if not found_intersection:
                    # If no intersection was found, return the lowest level
                    lowest_level = sorted_levels[-1]  # Get the lowest level
                    results.append({
                        'Element ID': element_id,
                        'Reference Level': lowest_level,
                    })
        else:
            print('Element ID {} does not have curves.'.format(element_id))

    return results


# Add the functions to the main logic
def main():
    selected_categories, run_button_clicked = show_window(sorted_category_items)

    if not run_button_clicked:
        script.exit()

    if not selected_categories:
        forms.alert('No categories selected', title='Select Categories')
        script.exit()

    # Get the selected category names
    selected_category_names = [category.Name for category in selected_categories]

    # Initialize lists for grouping elements
    global level_and_elevation_elements
    level_and_elevation_elements = []
    global reference_level_elements
    reference_level_elements = []

    # Allow the user to select elements belonging to the selected categories
    while True: # Loop to keep the selection filter active
        try:
            with forms.WarningBar(title='Select elements and press Finish when complete'):
                filter = CategorySelectionFilter(selected_category_names)
                selected_ids = uidoc.Selection.PickObjects(ObjectType.Element, filter, 'Select Elements')
                selected_elements = [doc.GetElement(id.ElementId) for id in selected_ids]

            if not selected_elements:  # No elements selected or operation canceled
                forms.alert('No elements have been selected', title='Select Elements')
                continue

            # Iterate over the selected elements and check parameters
            for element in selected_elements:
                # Get Level, Elevation from Level, and Reference Level parameters
                level_param = element.get_Parameter(LEVEL_PARAM)
                elevation_param = element.get_Parameter(ELEVATION_PARAM)
                reference_level_param = element.get_Parameter(REFERENCE_LEVEL_PARAM)

                # Retrieve and format parameter values
                level_value = level_param.AsValueString() if level_param else None
                elevation_value = elevation_param.AsDouble() if elevation_param else None
                reference_level_value = reference_level_param.AsValueString() if reference_level_param else None

                # Determine group based on parameters
                if level_value and elevation_value is not None:
                    level_and_elevation_elements.append({
                        'Element ID': element.Id,
                        'Level': level_value,
                        'Elevation from Level (mm)': elevation_value,
                    })
                elif reference_level_value:
                    reference_level_elements.append({
                        'Element ID': element.Id,
                        'Reference Level': reference_level_value
                    })

            # Create a transaction group
            with TransactionGroup(doc, __title__) as tg:
                tg.Start()

                # Analyze the elements with Reference Levels using curves and update the parameter within a transaction
                with Transaction(doc, 'Set Reference Level Parameter') as t1:
                    t1.Start()
                    results = identify_reference_level()

                    try:
                        for result in results:
                            element_id = result['Element ID']
                            # Check if 'Reference Level' exists in the dictionary
                            if 'Reference Level' in result:
                                reference_level = result['Reference Level']
                                element = doc.GetElement(element_id)
                                reference_level_param = element.get_Parameter(REFERENCE_LEVEL_PARAM)

                                if reference_level_param:
                                    reference_level_param.Set(reference_level.Id)

                        t1.Commit()
                    
                    except Exception as e:
                        t1.RollBack()
                        print('An error occurred:', e)
                        tg.RollBack()
                        raise 

                # Analyze the elements with Level and Elevation from Level and update the parameter within a transaction
                with Transaction(doc, 'Set Level and Elevation from Level Parameters') as t2:
                    t2.Start()
                    results = identify_level_and_elevation_from_level()

                    try:
                        for result in results:
                            element_id = result['Element ID']
                            # Check if 'Level' exists in the dictionary
                            if 'Level' in result:
                                level = result['Level']
                                elevation_from_level = result['Elevation from Level']
                                element = doc.GetElement(element_id)
                                level_param = element.get_Parameter(LEVEL_PARAM)
                                elevation_param = element.get_Parameter(ELEVATION_PARAM)

                                if level_param:
                                    level_param.Set(level.Id)
                                if elevation_param:
                                    elevation_param.Set(elevation_from_level)

                        t2.Commit()
                    
                    except Exception as e:
                        t2.RollBack()
                        print('An error occurred:', e)
                        tg.RollBack()
                        raise  

                tg.Assimilate()

            # Calculate the total number of updated elements
            total_updated_elements = len(reference_level_elements) + len(level_and_elevation_elements)

            # Determine the message based on the number of updated elements
            if total_updated_elements > 0:
                if total_updated_elements == 1:
                    message = "You updated 1 element!"
                else:
                    message = "You updated {} elements!".format(total_updated_elements)
                forms.alert(message, title='Success')
            else:
                forms.alert("You haven't updated any elements", title='Info')

        except OperationCanceledException:
            forms.alert('User cancelled selection', title='Select elements')
        break
if __name__ == '__main__':
    main()
