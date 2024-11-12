# -*- coding: utf-8 -*-
__title__ = 'Batch Load\nFamilies'
__author__ = "PAM Building UK"
__doc__ = """Version = 1.0
Date    = 01.08.2024
__________________________________________________________________
Compatibility:

Revit 2023+
__________________________________________________________________
Description:

Batch load families from folder

Note:
Please be as specific as possible selecting the folder,
as this script will load all the families from sub-folders as well.
__________________________________________________________________
How-to:

-> Click the button
-> Select folder location
-> Click 'OK'
__________________________________________________________________
"""

# Add references to required Revit API libraries and import required classes from Revit API and pyRevit
import clr

# from Autodesk.Revit.UI import *
from Autodesk.Revit.DB import Transaction, \
                            IFamilyLoadOptions
#from Autodesk.Revit.Exceptions import OperationCanceledException

# Import Python modules
import os
import re

# Import libraries to create a Windows form
clr.AddReference("System.Windows.Forms")
#clr.AddReference("System.Drawing")

from System.Windows.Forms import FolderBrowserDialog, DialogResult

from pyrevit import revit, forms

# Variables
uidoc = revit.uidoc
doc = revit.doc

# Store user specified path
directory = ""

# Create folder browser window 
dialog = FolderBrowserDialog()

# Record for user action and store selected path
dialogResult = dialog.ShowDialog()

if (dialogResult == DialogResult.OK):
    directory = dialog.SelectedPath

    # Retrieve all pathfiles and names from directory and subdirectories
    def retrieveFamilies(directory):
        familiesNames = list()
        for folderName, subFolders, files in os.walk(directory):
            # Check if there are Revit families
            families = re.compile(r"[^{ddd+}]\.rfa$")
            for file in files:
                # Assign matched files to a variable
                matched = families.search(file)
                if matched:
                    # Get path of families
                    filePath = os.path.join(folderName, file)
                    familiesNames.append(filePath)
        return familiesNames

    # Call function to search for families in path and subfolders
    familiesList = retrieveFamilies(directory)

    # Check if families were found in the selected folder
    if familiesList:
        # Class to define loading options
        class familyLoadOptions(IFamilyLoadOptions):
            def __init__(self, overwrite):
                self.bool = overwrite
            def OnFamilyFound(self, bool1, bool2):
                return self.bool
            def OnSharedFamilyFound(self, sfamily, bool1, familySource, bool2):
                return self.bool

        # Create a individual transaction to change the parameters on sheet
        t = Transaction(doc, "Batch Load Families")
        # Start individual transaction
        t.Start()

        # Loop through families and load them into the project
        loadedFam = list()
        notLoadedFam = list()

        for family in familiesList:
            try:
                doc.LoadFamily(family, familyLoadOptions(True))
                loadedFam.append(family)
            except Exception as ex:
                forms.alert("Error: " + str(ex))

        # Commit individual transaction
        t.Commit()

        # Check if any families were loaded successfully
        if loadedFam:
            print("You loaded {} families:\n{}".format(len(loadedFam), "\n".join(loadedFam)))
        else:
            forms.alert('No Revit families found in that folder', title='No Revit Families')
    else:
        forms.alert('No Revit families found in that folder', title='No Revit Families')
elif (dialogResult == DialogResult.Cancel):
    forms.alert('No folder selected', title='Select Folder Location')
