# -*- coding: utf-8 -*-
__title__ = "Remove Access Doors"

# Add imports
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Plumbing import Pipe
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.Exceptions import OperationCanceledException

from pyrevit import revit, forms

# Variables
uidoc = revit.uidoc
doc = revit.doc

# Additional variables
connected_pipes = set()  # Set to keep track of pipes being connected

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> SELECTION FILTER
class FittingsSelectionFilter(ISelectionFilter):
    """Filter class to allow selection of pipe fittings only."""
    def AllowElement(self, element):
        return element.Category and element.Category.Name == "Pipe Fittings"
    
    def AllowReference(self, reference, position):
        return False

def getConnectors(element):
    """Retrieve connectors from the given element.""" 
    connectors = []
    try:
        connectors = element.MEPModel.ConnectorManager.Connectors
    except AttributeError:
        try:
            connectors = element.ConnectorManager.Connectors
        except AttributeError:
            connectors = []
    return connectors

def getConnectedConnectors(connector):
    """Retrieve connected connectors from the given connector."""
    connected_connectors = []
    try:
        for ref in connector.AllRefs:
            if ref.Owner.Id != connector.Owner.Id and ref.ConnectorType != ConnectorType.Logical:
                connected_connectors.append(ref)
    except Exception:
        pass  # Suppressing error print for cleaner output
    
    return connected_connectors

def getMostDistantConnectors(group):
    """Find the two most distant connectors in the group.""" 
    lstCon = []
    for elem_id in group:
        element = doc.GetElement(elem_id)
        connectors = getConnectors(element)
        lstCon.extend(connectors)
    
    # Only consider pairs of distinct connectors
    pairLst = [[x, y] for x in lstCon for y in lstCon if x != y]
    if pairLst:  # Ensure there are pairs to compare
        pairLst.sort(key=lambda x: x[0].Origin.DistanceTo(x[1].Origin))
        return pairLst[-1]  # Return the most distant pair of connectors
    return None

def RemoveUnionFitting(fitting):
    """Remove the specified fitting from the model.""" 
    try:
        doc.Delete(fitting.Id)
    except Exception:
        pass  # Suppressing error print for cleaner output

def getConnectTo(connector):
    """Return the connector to connect to, based on connector type.""" 
    for ref in connector.AllRefs:
        if ref.ConnectorType != ConnectorType.Logical and ref.Owner.Id != connector.Owner.Id:
            return ref
    return None

def main():
    connector_data = []  # List to store connector data
    selected_fitting_ids = []  # List to store selected fittings' IDs
    pipes_to_delete = []  # Standard Python list for pipes to delete

    while True:
        try:
            with forms.WarningBar(title='Select fittings and press Finish when complete'):
                filter = FittingsSelectionFilter()
                selected_ids = uidoc.Selection.PickObjects(ObjectType.Element, filter, 'Select Access Doors')
                selected_elements = [doc.GetElement(id.ElementId) for id in selected_ids]
                selected_fitting_ids = [element.Id for element in selected_elements]  # Store the IDs of selected fittings

            if not selected_ids:
                forms.alert('No fittings have been selected', title='Select Fittings')
                continue

            # Collecting the pipes to be connected
            for element in selected_elements:
                connectors = getConnectors(element)

                for connector in connectors:
                    # Retrieve connected connectors
                    connected_connectors = getConnectedConnectors(connector)
                    if connected_connectors:
                        for connected in connected_connectors:
                            # Only append connected pipes
                            if isinstance(connected.Owner, Pipe):
                                connector_data.append((connector.Owner.Id, connected.Owner.Id))  # Store pipe pairs

            # List to store pipe groups
            pipe_groups = []

            # Merging pipe pairs into groups
            for pipe1, pipe2 in connector_data:
                group_found = False
                groups_to_merge = []

                # Check if any existing group contains either pipe1 or pipe2
                for group in pipe_groups:
                    if pipe1 in group or pipe2 in group:
                        groups_to_merge.append(group)

                # If groups were found, merge them together with the new pipes
                if groups_to_merge:
                    # Merge all found groups into a single group
                    merged_group = set([pipe1, pipe2])
                    for group in groups_to_merge:
                        merged_group.update(group)
                        pipe_groups.remove(group)  # Remove the old groups that were merged

                    pipe_groups.append(merged_group)  # Add the merged group
                else:
                    # If no group contains these pipes, create a new group
                    pipe_groups.append(set([pipe1, pipe2]))

            # Start a transaction group to remove fittings and connect pipes
            with TransactionGroup(doc, __title__) as tg:
                tg.Start()

                # Count the number of fittings being removed
                fittings_removed_count = len(selected_elements)

                # Start a transaction to remove the fittings
                with Transaction(doc, "Remove Fittings") as t1:
                    t1.Start()
                    # Remove the selected fittings
                    for fitting in selected_elements:
                        RemoveUnionFitting(fitting)
                    t1.Commit()  # Commit the fitting removal transaction

                # Start another transaction to connect the most distant connectors
                with Transaction(doc, "Join Pipes") as t2:
                    t2.Start()

                    # For each group of pipes, find the most distant connectors and connect them
                    for group in pipe_groups:
                        if len(group) >= 2:  # Ensure there are at least 2 pipes to connect
                            most_distant_connectors = getMostDistantConnectors(group)

                            if most_distant_connectors:
                                conA, conB = most_distant_connectors
                                pipeA = conA.Owner

                                # Get the second connector of pipeA and connect it to the distant connector of pipeB
                                secondConPipeA = [x for x in pipeA.ConnectorManager.Connectors if x.Id != conA.Id][0]
                                conToConnect = getConnectTo(conB)

                                # Join pipes
                                if conToConnect:
                                    secondConPipeA.ConnectTo(conToConnect)
                                    secondConPipeA.Origin = conToConnect.Origin
                                else:
                                    secondConPipeA.Origin = conB.Origin

                                connected_pipes.add(pipeA.Id)  # Track connected pipe
                                connected_pipes.add(conB.Owner.Id)  # Track connected pipe

                    t2.Commit()  # Commit the connection transaction

                # Collect pipes to delete, ensuring we don't include connected pipes or selected fittings
                for group in pipe_groups:
                    for pipe in group:
                        if pipe not in connected_pipes and pipe not in selected_fitting_ids:  # Only add pipes not being connected or selected fittings
                            pipes_to_delete.append(pipe)

                # After connecting pipes, check for any additional redundant pipes
                for pipe_id in connected_pipes:
                    connected_pipe = doc.GetElement(pipe_id)
                    if connected_pipe:
                        # Get connectors for the connected pipe
                        connectors = getConnectors(connected_pipe)
                        # Check if the connected pipe has other connected elements
                        for connector in connectors:
                            if not getConnectedConnectors(connector):  # If it has no other connected elements
                                pipes_to_delete.append(connected_pipe.Id)

                # Delete the redundant pipes after joining
                if pipes_to_delete:
                    with Transaction(doc, 'Delete Redundant Pipes') as t3:
                        t3.Start()
                        for pipe_id in pipes_to_delete:
                            # Check if the element still exists in the document before deleting
                            pipe_to_delete = doc.GetElement(pipe_id)
                            if pipe_to_delete is not None:
                                doc.Delete(pipe_id)
                        t3.Commit()

                tg.Assimilate()  # Commit the entire transaction group

            # Determine the message based on the number of fittings removed
            if fittings_removed_count > 0:
                if fittings_removed_count == 1:
                    message = "You removed 1 element!"
                else:
                    message = "You removed {} elements!".format(fittings_removed_count)
                forms.alert(message, title='Success')
            else:
                forms.alert("You haven't removed any elements", title='Info')

            break  # Exit the loop after processing the connections

        except OperationCanceledException:
            forms.alert('User cancelled selection', title='Select elements')
            break
        except Exception as e:
            forms.alert(str(e), title='Error')
            break

# Run the main selection function
main()
