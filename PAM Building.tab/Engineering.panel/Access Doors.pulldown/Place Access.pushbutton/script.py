# -*- coding: utf-8 -*-
__title__ = "Place Access Doors"
__author__ = "PAM Building UK"
__doc__ = """Version = 1.0
Date    = 01.08.2024
__________________________________________________________________
Compatibility:

Revit 2023+
__________________________________________________________________
Description:

Places access doors at specified elevation above selected levels.
__________________________________________________________________
How-to:

-> Click the button
-> Select the pipes on which you want to place access doors and press 'Finish'
-> Input elevation above the levels, then select the levels and press 'Place Access Doors' button
__________________________________________________________________
"""

# Add imports
import os
import clr
import webbrowser

# Add references to the necessary assemblies
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')

from System.Windows.Controls import Button, Image, ListBox
from System.Windows.Input import MouseButtonState

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.Exceptions import OperationCanceledException

from pyrevit import revit, forms, DB
from pyrevit.forms import WPFWindow

# Variables
uidoc = revit.uidoc
doc = revit.doc

class LevelItem:
    """Class to represent a level item in the ListBox."""
    def __init__(self, level):
        self.Level = level
        self.IsChecked = False
        # Convert elevation from feet to millimeters using UnitUtils
        elevation_in_mm = UnitUtils.Convert(level.Elevation, UnitTypeId.Feet, UnitTypeId.Millimeters)
        self.Name = "{}, Elevation {} mm".format(level.Name, int(round(elevation_in_mm)))  # Format name with elevation in mm

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> SELECTION FILTER
class SelectionFilter(ISelectionFilter):
    """Filter class to allow selection of pipes only."""
    def AllowElement(self, element):
        return element.Category and element.Category.Name == "Pipes"
    
    def AllowReference(self, reference, position):
        return False

def GetBoundingBox(element):
    if not isinstance(element, FamilyInstance):
        return None

    bbox = element.get_BoundingBox(doc.ActiveView)
    if bbox:
        return bbox
    return None

def BoundingBoxIntersects(bbox1, bbox2):
    if not bbox1 or not bbox2:
        return False

    return (bbox1.Max.X >= bbox2.Min.X and
            bbox1.Min.X <= bbox2.Max.X and
            bbox1.Max.Y >= bbox2.Min.Y and
            bbox1.Min.Y <= bbox2.Max.Y and
            bbox1.Max.Z >= bbox2.Min.Z and
            bbox1.Min.Z <= bbox2.Max.Z)

def IntersectionPlaneAndLine(plane, line):
    planePoint = plane.Origin
    planeNormal = plane.Normal
    lineStart = line.GetEndPoint(0)
    lineEnd = line.GetEndPoint(1)
    lineDirection = (lineEnd - lineStart).Normalize()

    if planeNormal.DotProduct(lineDirection) == 0:
        return None

    lineParameter = (planeNormal.DotProduct(planePoint) - planeNormal.DotProduct(lineStart)) / planeNormal.DotProduct(
        lineDirection)
    return lineStart + lineParameter * lineDirection

def GetZCoordinate(point):
    return point.Z

def SortPointByElevation(points):
    return sorted(points, key=GetZCoordinate)

def SortPointByLineDirection(line, lstPoint):
    direction = line.Direction
    vectorZ = direction.Z
    sortedPoints = SortPointByElevation(lstPoint)
    if vectorZ > 0:
        return sortedPoints
    else:
        return list(reversed(sortedPoints))

def SplitPipeByPoint(pipe, pts):
    ele = []
    with Transaction(doc, 'Break Curve') as t:
        t.Start()
        result = []
        for pt in pts:
            try:
                ele.append(DB.Plumbing.PlumbingUtils.BreakCurve(doc, pipe.Id, pt))
            except Exception as er:
                result.append(er)
        ele.append(pipe.Id)
        result = [doc.GetElement(Id) for Id in ele]
        t.Commit()
    return result

def SplitDuctByPoint(duct, pts):
    ele = []
    with Transaction(doc, 'Break Curve') as t:
        t.Start()
        result = []
        for pt in pts:
            try:
                ele.append(DB.Mechanical.MechanicalUtils.BreakCurve(doc, duct.Id, pt))
            except Exception as er:
                result.append(er)
        ele.append(duct.Id)
        result = [doc.GetElement(Id) for Id in ele]
        t.Commit()
    return result

def ClosestConnectors(ele1, ele2):
    conn1 = ele1.ConnectorManager.Connectors
    conn2 = ele2.ConnectorManager.Connectors

    dist = 100000000
    connset = None
    for c in conn1:
        for d in conn2:
            conndist = c.Origin.DistanceTo(d.Origin)
            if conndist < dist:
                dist = conndist
                connset = [c, d]
    return connset

def CreateUnionFitting(ele1, ele2):
    connectors = ClosestConnectors(ele1, ele2)
    result = []
    with Transaction(doc, 'Create Union Fitting') as t:
        t.Start()
        try:
            result.append(doc.Create.NewUnionFitting(connectors[0], connectors[1]))
        except Exception as er:
            result.append(er)
        t.Commit()
    return result

def get_sorted_levels(doc):
    levels = FilteredElementCollector(doc).OfClass(Level).ToElements()
    return sorted(levels, key=lambda lvl: lvl.ProjectElevation)

def show_window(selected_elements):
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
        run_button_clicked[0] = True  # Set the flag to indicate the run button was clicked
        elevation_text = window.FindName('input_elevation').Text
        try:
            #Convert text to float and get the value in feet
            elevation = float(elevation_text) / 304.8
        except ValueError:
            forms.alert('Please enter a numeric value', title='Invalid Input for Elevation')
            return
        
        list_box = window.FindName('list_levels')
        if list_box:
            selected_levels = [item.Level for item in list_box.Items if isinstance(item, LevelItem) and item.IsChecked]
            if not selected_levels:
                forms.alert('No levels selected', title='Select Levels')
                return
        
        # Close the window and return selected data
        window.DialogResult = True
        window.Tag = (selected_levels, elevation)
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
        list_box = window.FindName('list_levels')
        if list_box and isinstance(list_box, ListBox):
            for item in list_box.Items:
                if isinstance(item, LevelItem):
                    item.IsChecked = True
            list_box.Items.Refresh()  # Refresh the ListBox to reflect changes

    def uncheck_all_click(sender, args):
        """Handle the uncheck all button click event."""
        list_box = window.FindName('list_levels')
        if list_box and isinstance(list_box, ListBox):
            for item in list_box.Items:
                if isinstance(item, LevelItem):
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

    # Populate ListBox with levels
    list_box = window.FindName('list_levels')
    if list_box and isinstance(list_box, ListBox):
        levels = get_sorted_levels(doc)
        for level in levels:
            list_box.Items.Add(LevelItem(level))

    # Show the window
    window.ShowDialog()

    # Retrieve and return selected levels and elevation
    if window.DialogResult:
        return window.Tag, run_button_clicked[0]
    else:
        return None, run_button_clicked[0]

# Main Logic
def main():
    while True: # Loop to keep the selection filter active
        try:
            with forms.WarningBar(title='Select pipes and press Finish when complete'):
                filter = SelectionFilter()
                selected_ids = uidoc.Selection.PickObjects(ObjectType.Element, filter, 'Select Pipes')
                selected_elements = [doc.GetElement(id.ElementId) for id in selected_ids]

            if not selected_ids:  # No pipe fittings selected or operation cancelled
                forms.alert('No pipes have been selected', title='Select Pipes')
                continue
            else:
                selected_data, run_button_clicked = show_window(selected_elements)
                if run_button_clicked:  # Only proceed if the Run button was clicked
                    if selected_data:
                        selected_levels, elevation = selected_data
                        if selected_levels is None:
                            forms.alert('No levels have been selected', title='Select Levels')
                            return
                        
                        # Retrieve element lines
                        eleLine = [ele.Location.Curve for ele in selected_elements]
                        
                        # Create planes for each selected level 
                        planeLst = []
                        z_axis = XYZ(0, 0, 1)
                        for level in selected_levels:
                            plane = Plane.CreateByNormalAndOrigin(z_axis, XYZ(0, 0, level.Elevation + elevation))
                            planeLst.append(plane)
                        
                        # Find intersections between lines and planes
                        intersectionPoints = []
                        for line in eleLine:
                            sublst = []
                            for plane in planeLst:
                                point = IntersectionPlaneAndLine(plane, line)
                                if point:
                                    sublst.append(point)
                            sorted_points = SortPointByLineDirection(line, sublst)
                            intersectionPoints.append(sorted_points)

                        # Place Access Doors
                        with TransactionGroup(doc, 'Place Access Doors') as tg:
                            tg.Start()
                            newEles = []
                            newEles2 = []
                            fittings_added = 0
                            fitting_data = []
                            for ele, sub_lst in zip(selected_elements, intersectionPoints):
                                if isinstance(ele, DB.Plumbing.Pipe):
                                    newEles = SplitPipeByPoint(ele, sub_lst)
                                    newEles2 = newEles[1:]
                                else:
                                    newEles = SplitDuctByPoint(ele, sub_lst)
                                    newEles2 = newEles[1:]
                                for ele1, ele2 in zip(newEles, newEles2):
                                    fittings = CreateUnionFitting(ele1, ele2)
                                    if fittings:
                                        fitting_data.extend(fittings)
                                    fittings_added += 1
                            
                            # Set 'Level' and 'Elevation from Level' parameters
                            with Transaction(doc, 'Set Level and Elevation') as t:
                                t.Start()
                                for fitting in fitting_data:
                                    if isinstance(fitting, FamilyInstance):
                                        fitting_bbox = GetBoundingBox(fitting)
                                        if fitting_bbox:
                                            fitting_level = None
                                            fitting_elevation = None
                                            for level in selected_levels:
                                                level_bbox = BoundingBoxXYZ()
                                                level_bbox.Min = XYZ(-10000, -10000, level.Elevation)
                                                level_bbox.Max = XYZ(10000, 10000, level.Elevation + elevation)
                                                if BoundingBoxIntersects(fitting_bbox, level_bbox):
                                                    fitting_level = level
                                                    fitting_elevation = elevation
                                                    break
                                            if fitting_level:
                                                fitting.get_Parameter(DB.BuiltInParameter.FAMILY_LEVEL_PARAM).Set(fitting_level.Id)
                                                fitting.LookupParameter('Elevation from Level').Set(fitting_elevation)
                                t.Commit()

                            tg.Assimilate()

                            # Determine the message based on the number of updated elements
                            if fittings_added > 0:
                                if fittings_added == 1:
                                    message = "You placed 1 access door!"
                                else:
                                    message = "You placed {} access doors!".format(fittings_added)
                                forms.alert(message, title='Success')
                            else:
                                forms.alert("You haven't placed any access doors", title='Info') 
                        
                        break  # Exit the loop if processing is complete

        except OperationCanceledException:
            forms.alert('User cancelled selection', title='Select Pipes')
        break
# Run the main function
main()