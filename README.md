# MayaAsciiParser
Maya Python script that allows importing of Maya ascii files scenes/models with out purging UNDO history and also allowing you to UNDO the import

This was written and tested for Maya 2025 and should work all the way to Maya 2022

## How to use

Copy the scripts to your script folder C:\Users\<username>\Documents\Maya\2025\scripts\MayaAsciiParser
```
from MayaAsciiParser import MayaAsciiParser
from maya import cmds
results = cmds.MayaAsciiImporter('C:/Users/MyAccount/Documents/Maya/projects/myvideogameproject/scenes/cube.ma')
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
