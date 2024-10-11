# MayaAsciiParser
Maya Python script that allows importing of Maya ascii files scenes/models with out purging UNDO history and also allowing you to UNDO the import

This was written and tested for Maya 2025 and should work all the way to Maya 2022

## How to use

Copy the scripts to your script folder C:\Users\<username>\Documents\Maya\2025\scripts\MayaAsciiParser

Include this into your script where importing assets begins.
```
from MayaAsciiParser import MayaAsciiParser
from maya import cmds
results = cmds.MayaAsciiImporter('C:/Users/MyAccount/Documents/Maya/projects/myvideogameproject/scenes/cube.ma')
```
Or as a stand alone toolbar script with file selection
```
from MayaAsciiParser import MayaAsciiParser
from importlib import reload
from maya import cmds
reload(MayaAsciiParser)
fileName=cmds.fileDialog2(ff="Maya Scene (*.ma)",cap='Import Maya Scene', ds=2,fm=1)
if(fileName != None):
    startT = cmds.timerX()
    cmds.MayaAsciiImporter(fileName[0])
    endT = cmds.timerX()
    print("Script completed at {0}".format( endT-startT))
```

Most Maya scene elements can be loaded with this script. Make sure the Maya scene files are not binary 

## Scene Compatible
- Skinned Models
- NURBS surfaces
- Curves
- BlendShapes
- Skeleton
- Nested Groups
- Meshes with multiple material faces
- Shaders

## Nodes Not Importable
- Script nodes

## Imported Shader groups
This script will only parse shaders that don't exist in the scene and plug the models to any existing materials.
