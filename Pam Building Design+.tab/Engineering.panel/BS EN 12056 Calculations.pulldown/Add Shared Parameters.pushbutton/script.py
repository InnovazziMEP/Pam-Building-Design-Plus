# -*- coding: utf-8 -*-
__title__ = "Add Shared Parameters"

import os
import clr
import webbrowser

clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')

from System.Windows.Controls import Button, TextBox, Image, ListBox
from System.Windows.Input import MouseButtonState

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import UIApplication
from Autodesk.Revit.UI.Selection import *

from pyrevit import revit, forms, script
from pyrevit.forms import WPFWindow

# 📦 Variables
app = __revit__.Application  # type: UIApplication
doc = revit.doc

operation_cancelled = False  # Initialize cancellation flag

class ParameterGroupItem:
    """Class to represent a parameter group item in the ListBox."""
    def __init__(self, name, group):
        self.Name = name
        self.Group = group
        self.IsChecked = False

# 📁 Access shared parameter file
sp_file = app.OpenSharedParameterFile()

if sp_file is None:
    forms.alert('Shared parameter file is not set or cannot be accessed.', title='Error')
    script.exit()

# 🔍 List all parameter groups in the shared parameter file
sp_groups = sp_file.Groups

def show_window():
    """Load and display the WPF window for user interaction."""
    script_dir = os.path.dirname(__file__)
    xaml_file_path = os.path.join(script_dir, 'UI.xaml')

    window = WPFWindow(xaml_file_path)

    def close_button_click(sender, args):
        """Handle the close button click event."""
        global operation_cancelled
        operation_cancelled = True
        window.Close()

    def run_button_click(sender, args):
        """Handle the Add Parameters button click event."""
        # Check selected parameter group
        list_box_group = window.FindName('list_parametergroups')
        if list_box_group:
            selected_items = [item for item in list_box_group.Items if isinstance(item, ParameterGroupItem) and item.IsChecked]
            if selected_items:
                selected_parameter_group = selected_items[0]  # Only one group can be selected
            else:
                forms.alert('No parameter group selected', title='Select Parameter Group')
                return

        # Set the window result and tag for return
        window.DialogResult = True
        window.Tag = selected_parameter_group.Group  # Only return the selected group
        window.Close()
    
    def on_image_click(sender, event_args):
        """Handle the image click event to open a URL."""
        url = "https://www.pambuilding.co.uk"
        webbrowser.open(url)

    def header_drag(sender, event_args):
        """Allow dragging the window by the header."""
        if event_args.LeftButton == MouseButtonState.Pressed:
            window.DragMove()

    def UI_text_filter_updated(sender, args):
        """Handle TextBox TextChanged event to filter ListBox items."""
        filter_text = sender.Text.lower()
        list_box = window.FindName('list_parametergroups')
        list_box.Items.Clear()
        for item in sp_groups:
            if filter_text in item.Name.lower():
                list_box.Items.Add(ParameterGroupItem(item.Name, item))

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
    
    # Attach the TextChanged event handler to the TextBox in code
    text_box = window.FindName('textbox_filter')
    if text_box and isinstance(text_box, TextBox):
        text_box.TextChanged += UI_text_filter_updated
            
    # Populate ListBox with parameter groups from shared parameter file
    list_box = window.FindName('list_parametergroups')
    if list_box and isinstance(list_box, ListBox):
        for group in sorted(sp_groups, key=lambda g: g.Name):  # Sort groups by name
            item = ParameterGroupItem(group.Name, group)
            list_box.Items.Add(item)

    # Show the window
    window.ShowDialog()

    # Retrieve and return selected parameter group
    if window.DialogResult:
        return window.Tag
    else:
        return None

# Show the custom window and get the selected parameter group
selected_parameter_group = show_window()

if operation_cancelled:
    # Skip further processing if the operation was cancelled
    script.exit()

if selected_parameter_group:
    # 👉 Create Category Set 
    cats = doc.Settings.Categories
    cat_pipes = cats.get_Item(BuiltInCategory.OST_PipeCurves)  # Only Pipe Curves (Pipes)
    cat_set = app.Create.NewCategorySet()
    cat_set.Insert(cat_pipes)

    # 🔍 Find or Create Parameter Group in Shared Parameter File
    target_group = selected_parameter_group

    # List of parameters with their disciplines and types
    parameters_to_add = [
        ("EN12056_Discharge Units", SpecTypeId.Number, BuiltInParameterGroup.PG_PLUMBING),
        ("EN12056_Frequency Factor", SpecTypeId.Number, BuiltInParameterGroup.PG_PLUMBING), 
        ("EN12056_Continuous Flow Rate", SpecTypeId.Flow, BuiltInParameterGroup.PG_PLUMBING),
        ("EN12056_Pumped Flow Rate", SpecTypeId.Flow, BuiltInParameterGroup.PG_PLUMBING),
        ("EN12056_Waste Water Flow Rate", SpecTypeId.Flow, BuiltInParameterGroup.PG_PLUMBING),
        ("EN12056_Total Flow Rate", SpecTypeId.Flow, BuiltInParameterGroup.PG_PLUMBING), 
        ("EN12056_Primary Ventilated System", SpecTypeId.Boolean.YesNo, BuiltInParameterGroup.PG_PLUMBING),
        ("EN12056_Secondary Ventilated System", SpecTypeId.Boolean.YesNo, BuiltInParameterGroup.PG_PLUMBING),
    ]

    added_to_spf = 0
    added_to_project = 0

    try:
        # 🔓 Start Transaction
        t = Transaction(doc, __title__)
        t.Start()

        for param_name, param_type, param_group in parameters_to_add:
            param_exists_in_spf = False
            param_exists_in_project = False
            new_param_def = None

            # Check if the parameter already exists in the shared parameter file
            for sp_group in sp_file.Groups:
                for p_def in sp_group.Definitions:
                    if p_def.Name == param_name:
                        param_exists_in_spf = True
                        new_param_def = p_def
                        break
                if param_exists_in_spf:
                    break

            if not param_exists_in_spf:
                try:
                    # Create new parameter definition options
                    external_def_opts = ExternalDefinitionCreationOptions(param_name, param_type)
                    external_def_opts.Visible = True
                    external_def_opts.UserModifiable = True
                    new_param_def = target_group.Definitions.Create(external_def_opts)
                    added_to_spf += 1
                except Exception as e:
                    continue

            # Bind parameter to project categories if it doesn't already exist in project
            if new_param_def:
                bindings = doc.ParameterBindings
                iterator = bindings.ForwardIterator()
                while iterator.MoveNext():
                    binding_def = iterator.Key
                    if binding_def.Name == param_name:
                        param_exists_in_project = True
                        break

                if not param_exists_in_project:
                    new_instance_binding = app.Create.NewInstanceBinding(cat_set)

                    # Insert the parameter under the relevant group
                    success = doc.ParameterBindings.Insert(
                        new_param_def, 
                        new_instance_binding, 
                        param_group
                    )           
                    added_to_project += 1

        t.Commit()

        # 🚨 Show alert based on results
        if added_to_spf == 0 and added_to_project == 0:
            forms.alert('No parameters added to the shared parameter file or project', title='Info')
        elif added_to_spf > 0 and added_to_project == 0:
            forms.alert('Parameters added to the shared parameter file', title='Success')
        elif added_to_spf == 0 and added_to_project > 0:
            forms.alert('Parameters added to the project', title='Success')
        else:
            forms.alert('Parameters added to the shared parameter file and to the project', title='Success')

    except Exception as e:
        print('🚫 Transaction failed: {}'.format(e))
        t.RollBack()
        print("🔄 Transaction rolled back.")
