# -*- coding: utf-8 -*- 
__title__ = "BS EN 12056-2 Calculations"

import os
import math
import webbrowser
import re

import clr

clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')

from System.Windows.Controls import Button, TextBox, Image, ListBox
from System.Windows.Input import MouseButtonState

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter

from pyrevit import revit, forms, script
from pyrevit.forms import WPFWindow

# 📦 Variables
app = __revit__.Application
uidoc = revit.uidoc
doc = revit.doc

operation_cancelled = False  # Initialize cancellation flag

# Define a piping system to show in the UI
class PipingSystemItem:
    """Class to represent a piping system item in the ListBox."""
    def __init__(self, name, system):
        self.Name = name
        self.System = system
        self.IsChecked = False

# Define a selection filter to allow the user to select only pipes, pipe fittings, pipe accessories, and plumbing fixtures
class CategorySelectionFilter(ISelectionFilter):
    def __init__(self):
        self.category_names = ["Pipes", "Pipe Fittings", "Pipe Accessories", "Plumbing Fixtures"]
    def AllowElement(self, element):
        if element.Category is not None and element.Category.Name in self.category_names:
            return True
        else:
            return False
    def AllowReference(self, ref, point):
        return True

# Function to get element size
def getSize(x):
    try:
        conns = x.ConnectorManager.Connectors
    except:
        conns = x.MEPModel.ConnectorManager.Connectors
    maxsize = 0
    for c in conns:
        if c.Shape != ConnectorProfileType.Round:
            continue
        else:
            startsize = c.Radius * 2
            if startsize > maxsize:
                maxsize = startsize
    return maxsize

factor = 99999

# Function to find the next element in the system
def nextElement(elem, sys):
    sysname = elem.get_Parameter(BuiltInParameter.RBS_SYSTEM_CLASSIFICATION_PARAM).AsString()
    for s in sysname.split(","):
        if s in sys.split(","):
            break
    else:
        return 4
    if "Return" in sysname or "Sanitary" in sysname:
        direction = FlowDirectionType.In
    else:
        direction = FlowDirectionType.Out
    try:
        connectors = elem.ConnectorManager.Connectors
        for conn in connectors:
            if conn.Domain != Domain.DomainPiping:
                continue
            elif conn.Direction == direction:
                continue
            else:
                endconn = conn
        for c in endconn.AllRefs:
            if c.Owner.Id.Equals(elem.Id):
                continue
            elif c.Owner.GetType() == Mechanical.MechanicalSystem or c.Owner.GetType() == Plumbing.PipingSystem:
                return 0
            else:
                newelem = c.Owner
                return newelem
    except AttributeError:
        connectors = elem.MEPModel.ConnectorManager.Connectors
        if connectors.Size == 1:
            for conn in connectors:
                if conn.Domain != Domain.DomainPiping:
                    continue
                endconn = conn
            if endconn.AllRefs.Size == 1:
                for c in endconn.AllRefs:
                    if c.Owner.GetType() == Mechanical.MechanicalSystem or c.Owner.GetType() == Plumbing.PipingSystem:
                        return 1
            for c in endconn.AllRefs:
                if c.Owner.Id.Equals(elem.Id):
                    continue
                elif c.Owner.GetType() == Mechanical.MechanicalSystem or c.Owner.GetType() == Plumbing.PipingSystem:
                    continue
                else:
                    newelem = c.Owner
                    return newelem
        elif connectors.Size == 2:
            for conn in connectors:
                if conn.Domain != Domain.DomainPiping:
                    continue
                if conn.Direction == direction:
                    continue
                else:
                    endconn = conn
            if endconn.AllRefs.Size == 1:
                for c in endconn.AllRefs:
                    if c.Owner.GetType() == Mechanical.MechanicalSystem or c.Owner.GetType() == Plumbing.PipingSystem:
                        return 2
            for c in endconn.AllRefs:
                if c.Owner.Id.Equals(elem.Id):
                    continue
                elif c.Owner.GetType() == Mechanical.MechanicalSystem or c.Owner.GetType() == Plumbing.PipingSystem:
                    continue
                else:
                    newelem = c.Owner
                    return newelem
        else:
            for conn in connectors:
                if conn.Domain != Domain.DomainPiping:
                    continue
                if conn.Direction != direction:
                    endconn = conn
            if endconn.AllRefs.Size == 1:
                for c in endconn.AllRefs:
                    if c.Owner.GetType() == Mechanical.MechanicalSystem or c.Owner.GetType() == Plumbing.PipingSystem:
                        return 3
            for c in endconn.AllRefs:
                if c.Owner.Id.Equals(elem.Id):
                    continue
                elif c.Owner.GetType() == Mechanical.MechanicalSystem or c.Owner.GetType() == Plumbing.PipingSystem:
                    continue
                else:
                    newelem = c.Owner
                    return newelem
                
# Function to get system classification
def get_system_classification(element):
    classification_param = element.get_Parameter(BuiltInParameter.RBS_SYSTEM_CLASSIFICATION_PARAM)
    if classification_param:
        return classification_param.AsString()
    return None

def natural_sort_key(system_name):
    """Sorts strings containing numbers in natural order.""" 
    return [int(text) if text.isdigit() else text for text in re.split(r'(\d+)', system_name)]

# Retrieve all piping systems in the project
piping_systems_collector = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_PipingSystem).WhereElementIsNotElementType()

# Define the system classification we're looking for
sanitary_classification_name = "Sanitary"

# Filter piping systems by 'Sanitary' system classification
piping_systems = []
for system in piping_systems_collector:
    # Retrieve the system classification parameter
    system_classification_param = system.get_Parameter(BuiltInParameter.RBS_SYSTEM_CLASSIFICATION_PARAM)
    
    if system_classification_param:
        # Get the string value of the classification and check if it matches 'Sanitary'
        system_classification_name = system_classification_param.AsValueString()  # This retrieves the classification as a readable string
        if system_classification_name == sanitary_classification_name:
            piping_systems.append(system)

def show_first_ui():
    """Load and display the WPF window for user interaction."""
    script_dir = os.path.dirname(__file__)
    xaml_file_path = os.path.join(script_dir, 'UI1.xaml')

    window = WPFWindow(xaml_file_path)

    def close_button_click(sender, args):
        """Handle the close button click event."""
        global operation_cancelled
        operation_cancelled = True
        window.Close()

    def run_button_click(sender, args):
        """Handle the Proceed button click event."""
        # Check selected piping system
        list_box_group = window.FindName('list_pipingsystems')
        if list_box_group:
            selected_items = [item for item in list_box_group.Items if isinstance(item, PipingSystemItem) and item.IsChecked]
            if selected_items:
                selected_piping_system = selected_items[0]  # Only one system can be selected
            else:
                forms.alert('No piping system selected', title='Select Piping System')
                return
        
        # Check selected system type
        selected_system_type = None
        if window.Primary.IsChecked:
            selected_system_type = "EN12056_Primary Ventilated System"
        elif window.Secondary.IsChecked:
            selected_system_type = "EN12056_Secondary Ventilated System"

        # Check selected K Factor
        selected_k_factor = None
        if window.Intermittent.IsChecked:
            selected_k_factor = 0.5
        elif window.Frequent.IsChecked:
            selected_k_factor = 0.7
        elif window.Congested.IsChecked:
            selected_k_factor = 1.0
        elif window.Special.IsChecked:
            selected_k_factor = 1.2
       
        # Set the window result and tag for return
        window.DialogResult = True
        window.Tag = {
            'piping_system': selected_piping_system,
            'system_type': selected_system_type,
            'k_factor': selected_k_factor,
        }
        window.Close()
    
    def on_image_click(sender, event_args):
        """Handle the image click event to open a URL."""
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
    logo_image = window.FindName('logo')
    if logo_image:
        logo_image.MouseLeftButtonDown += on_image_click

    # Find the TitleBar and attach the drag event handler
    title_bar = window.FindName('TitleBar')
    if title_bar:
        title_bar.MouseLeftButtonDown += header_drag

    # Populate ListBox with sanitary piping systems
    list_box = window.FindName('list_pipingsystems')
    if list_box and isinstance(list_box, ListBox):
        # Sort systems using natural numeric sorting
        for system in sorted(piping_systems, key=lambda s: natural_sort_key(s.Name)):
            item = PipingSystemItem(system.Name, system)
            list_box.Items.Add(item)

    # Show the window
    window.ShowDialog()

    # Retrieve and return the selected options
    if window.DialogResult:
        return window.Tag
    else:
        return None

def show_second_ui():
    """Load and display the WPF window for user interaction."""
    script_dir = os.path.dirname(__file__)
    xaml_file_path = os.path.join(script_dir, 'UI2.xaml')

    window = WPFWindow(xaml_file_path)

    def close_button_click(sender, args):
        """Handle the close button click event."""
        global operation_cancelled
        operation_cancelled = True
        window.Close()

    def run_button_click(sender, args):
        """Handle the Proceed button click event."""
        
        # Check which radio button is selected
        selected_discharge_type = None
        if window.Continuous.IsChecked:
            selected_discharge_type = "EN12056_Continuous Flow Rate"
        elif window.Pumped.IsChecked:
            selected_discharge_type = "EN12056_Pumped Flow Rate"
        else:
            forms.alert('Select continuous or pumped discharge', title='Select Option') 

        # Check flow rate value
        input_value = window.FindName('input_value')
        if input_value and isinstance(input_value, TextBox):
            flow_value_text = input_value.Text
            try:
                flow_value = float(flow_value_text)
            except ValueError:
                forms.alert('Please enter a numeric value', title='Invalid Input')
                return
        if selected_discharge_type:
            # Set the window result and tag for return
            window.DialogResult = True
            window.Tag = {
                'Qc or Qp': selected_discharge_type,
                'Flow value': flow_value
            }
            window.Close()
                
    def on_image_click(sender, event_args):
        """Handle the image click event to open a URL."""
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
    logo_image = window.FindName('logo')
    if logo_image:
        logo_image.MouseLeftButtonDown += on_image_click

    # Find the TitleBar and attach the drag event handler
    title_bar = window.FindName('TitleBar')
    if title_bar:
        title_bar.MouseLeftButtonDown += header_drag

    # Show the window
    window.ShowDialog()

    # Retrieve and return the selected options
    if window.DialogResult:
        return window.Tag
    else:
        return None

# Show the first UI and get the selected options
selected_1ui_options = show_first_ui()

# Check if the operation was cancelled or if no selection was made
if operation_cancelled or selected_1ui_options is None:
    # Skip further processing if the operation was cancelled
    script.exit()

# Access the selected piping system 
selected_piping_system = selected_1ui_options['piping_system'].System  # Access the Revit piping system

# Access the selected piping system and retrieve its PipingNetwork (returns an ElementSet)
network = selected_piping_system.PipingNetwork

# Define the list of required shared parameters
required_parameters = [
    "EN12056_Discharge Units", 
    "EN12056_Frequency Factor", 
    "EN12056_Continuous Flow Rate", 
    "EN12056_Pumped Flow Rate", 
    "EN12056_Waste Water Flow Rate", 
    "EN12056_Total Flow Rate", 
    "EN12056_Primary Ventilated System", 
    "EN12056_Secondary Ventilated System"
]

# Initialize a variable to store the first pipe element for parameter checking
first_pipe = None

# Iterate through the elements in the network and collect pipes only
pipes = []
for element in network:
    # Check if the element category is "Pipes"
    if element.Category and element.Category.Name == "Pipes":
        if first_pipe is None:
            first_pipe = element  # Store the first pipe element
        pipes.append(element)  # Store the actual element

# Check parameters if a pipe was found
if first_pipe:
    # Check if the first pipe has all the required parameters
    missing_parameters = False
    for param_name in required_parameters:
        param = first_pipe.LookupParameter(param_name)
        if param is None:
            missing_parameters = True
            break
    # Display an alert and exit if any parameters are missing
    if missing_parameters:
        forms.alert('Required parameters are missing!', title='Add Shared Parameters')
        script.exit()

# Access the selected options from first UI
selected_system_type = selected_1ui_options['system_type']
selected_k_factor = selected_1ui_options['k_factor']

# Example of handling the selected options
system_name = selected_piping_system.get_Parameter(BuiltInParameter.RBS_SYSTEM_NAME_PARAM).AsString()

# Main logic
# 🔓 Start a transaction group
with TransactionGroup(doc, __title__) as maintg:
    maintg.Start()
    
    # 🔓 Start a transaction for first sub-group
    with TransactionGroup(doc, 'Determine Qww') as firsttg:
        firsttg.Start()
        # 🔓 First transaction to reset parameters (t1)
        with Transaction(doc, 'Reset parameters') as t1:
            try:
                t1.Start()
                # Set parameter values to 0 for all required parameters across all pipes
                for pipe in pipes:
                    for param_name in required_parameters:
                        param = pipe.LookupParameter(param_name)
                        param.Set(0)  # Set the parameter value to 0          
                t1.Commit()  # Commit first transation
            except Exception as transaction_error:
                t1.RollBack()  # 🔄 Rollback in case of failure

        # 🔓 Second transaction to calculate Qww and and write parameters (t2)
        with Transaction(doc, 'Calculate Qww and write parameters') as t2:  
            try:
                t2.Start()
                # Iterate through pipes
                for pipe in pipes:
                    # Get the value of Fixture Units parameter
                    fixture_units_param = pipe.get_Parameter(BuiltInParameter.RBS_PIPE_FIXTURE_UNITS_PARAM)               
                    fixture_units_value = fixture_units_param.AsDouble()  # Retrieve the value as a double
                    # Write EN12056_Discharge Units parameter
                    discharge_units_param = pipe.LookupParameter('EN12056_Discharge Units')
                    discharge_units_param.Set(fixture_units_value)  # Set discharge units
                    # Write EN12056_Frequency Factor parameter
                    k_factor_param = pipe.LookupParameter('EN12056_Frequency Factor')
                    k_factor_param.Set(selected_k_factor)  # Set k factor
                    # Write EN12056_Primary Ventilated System or EN12056_Secondary Ventilated System parameter
                    system_type_param = pipe.LookupParameter(selected_system_type)
                    system_type_param.Set(1)  # Set primary or secondary ventilated system               
                    # Calculate Qww
                    Qww = selected_k_factor * math.sqrt(fixture_units_value)
                    Qww_converted = UnitUtils.ConvertToInternalUnits(Qww, UnitTypeId.LitersPerSecond)
                    # Write EN12056_Waste Water Flow Rate parameter
                    Qww_param = pipe.LookupParameter('EN12056_Waste Water Flow Rate')
                    Qww_param.Set(Qww_converted)  # Set Qww parameter
                    # Write EN12056_Total Flow Rate parameter
                    Qtot_param = pipe.LookupParameter('EN12056_Total Flow Rate')
                    Qtot_param.Set(Qww_converted)            
                t2.Commit()  # Commit second transaction
            except Exception as transaction_error:
                t2.RollBack()  # Rollback in case of failure
        
        firsttg.Assimilate()  # Finalize the transaction sub-group

    # Loop to handle continuous or pumped discharge
    while True:
        # Ask the user if they have continuous flow or pumped discharge
        continuous_or_pumped = forms.alert(
            "Add continuous flow or pumped discharge?",
            title="Continuous Flow or Pumped Discharge?",
            yes=True,
            no=True
        )
        if not continuous_or_pumped:
            break

        if continuous_or_pumped:  # If the user selects 'Yes'
            # Show the second UI and get the input
            selected_2ui_options = show_second_ui()

            # Check if the operation was cancelled or if no selection was made
            if operation_cancelled or selected_2ui_options is None:
                # Skip further processing if the operation was cancelled
                script.exit()
            # Process the input from the second UI
            discharge_type = selected_2ui_options.get('Qc or Qp')
            flow_value = selected_2ui_options.get('Flow value')

        # 🔓 Start a transaction for second sub-group
        with TransactionGroup(doc, 'Qc or Qp') as secondtg:
            secondtg.Start()

            # 🔓 Third transaction to add continuous flow or pumped discharge (t3)
            with Transaction(doc, 'Add Qc or Qp') as t3:
                try:
                    t3.Start() 
                    # Select elements downstream
                    if continuous_or_pumped:
                        def select_pipework():
                            with forms.WarningBar(title='Select element where continuous flow or pumped discharge enters the system'):
                                selection = uidoc.Selection
                                pipework_filter = CategorySelectionFilter()
                                selected_element_ref = selection.PickObject(ObjectType.Element, pipework_filter, "Select starting element")
                                selected_element = doc.GetElement(selected_element_ref)
                                return selected_element
                            
                        selected_element = select_pipework()
                        elements = [selected_element]
                        result = []
                        endlist = []

                        # Check if the selected element is a pipe and add it to the endlist
                        if hasattr(selected_element, 'Category') and selected_element.Category.Name == "Pipes":
                            endlist.append([selected_element]) 
                        for j, x in enumerate(elements):
                            listout = []
                            ids = []
                            sysclass = x.get_Parameter(BuiltInParameter.RBS_SYSTEM_CLASSIFICATION_PARAM).AsString()
                            startsize = getSize(x)
                            next = x
                            i = 0
                            while True:
                                if i > 1000:
                                    result.append(next.Id.ToString() + ": end of loop")
                                    break
                                try:
                                    next = nextElement(next, sysclass)
                                    i += 1
                                except Exception as e:
                                    result.append(next.Id.ToString() + ": probably a direction error")
                                    break
                                if isinstance(next, int):
                                    result.append(next.ToString() + ": open end or different system classification")
                                    break
                                if next.Id in ids:
                                    result.append(next.Id.ToString() + ": double element")
                                    break
                                nextsize = getSize(next)
                                if nextsize > startsize * factor:
                                    result.append(next.Id.ToString() + ": size end")
                                    break
                                ids.append(next.Id)
                                listout.append(next)
                            endlist.append(listout)

                        # Iterate through the elements in the network and collect pipes only
                        downstream_pipes = []
                        for sublist in endlist:
                            for element in sublist:
                                # Check if the element is of category "Pipes"
                                if element.Category.Name == "Pipes":
                                    downstream_pipes.append(element)  # Store the actual element

                        for pipe in downstream_pipes:
                            # Get EN12056_Continuous Flow Rate or EN12056_Pumped Flow Rate parameter and value
                            discharge_type_param = pipe.LookupParameter(discharge_type)
                            discharge_type_param_value = pipe.LookupParameter(discharge_type).AsDouble()
                            discharge_type_value_converted = UnitUtils.ConvertToInternalUnits(flow_value, UnitTypeId.LitersPerSecond)
                            # Add the new value to the existing value for EN12056_Continuous Flow Rate or EN12056_Pumped Flow Rate parameter
                            total_discharge_value = discharge_type_param_value + discharge_type_value_converted
                            discharge_type_param.Set(total_discharge_value)  # Update Qc or Qp with the accumulated value
                    t3.Commit()  # Commit third transaction
                except Exception as transaction_error:
                    t3.RollBack()  # Rollback in case of failure

            # 🔓 Last transaction to calculate Qtot and write EN12056_Total Flow Rate parameter
            with Transaction(doc, 'Calculate Qtot') as t4:
                try:
                    t4.Start()
                    # Calculate Qtot for all pipes in the system
                    for pipe in pipes:
                        # Retrieve the existing Qww parameter value for this pipe
                        Qww_param_value = pipe.LookupParameter('EN12056_Waste Water Flow Rate').AsDouble()
                        Qww = UnitUtils.ConvertFromInternalUnits(Qww_param_value, UnitTypeId.LitersPerSecond)
                        
                        # Calculate Qtot
                        Qc_param_value = pipe.LookupParameter('EN12056_Continuous Flow Rate').AsDouble()
                        Qc_converted = UnitUtils.ConvertFromInternalUnits(Qc_param_value, UnitTypeId.LitersPerSecond)
                        Qp_param_value = pipe.LookupParameter('EN12056_Pumped Flow Rate').AsDouble()
                        Qp_converted = UnitUtils.ConvertFromInternalUnits(Qp_param_value, UnitTypeId.LitersPerSecond)
                        Qtot = Qc_converted + Qp_converted + Qww
                        Qtot_converted = UnitUtils.ConvertToInternalUnits(Qtot, UnitTypeId.LitersPerSecond)
                        
                        # Write EN12056_Total Flow Rate parameter
                        Qtot_param = pipe.LookupParameter('EN12056_Total Flow Rate')
                        Qtot_param.Set(Qtot_converted)            
                    t4.Commit()  # Commit last transation
                except Exception as transaction_error:
                    t4.RollBack()  # 🔄 Rollback in case of failure

            secondtg.Assimilate()  # Finalize the transaction group

    maintg.Assimilate()  # Finalize the transaction group



