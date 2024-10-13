# Maya Mesh Importer
# Author : Shinobu
# Email: shinobu.bu@gmail.com
# Description: Imports the contents of a Maya ascii scene while preserving undo history
'''
Example code:
from MayaAsciiParser import MayaAsciiParser
from importlib import reload
from maya import cmds
reload(MayaAsciiParser)
results = cmds.MayaAsciiImporter('C:/Users/MyAccount/Documents/Maya/projects/myvideogameproject/scenes/cube.ma')

# or with file selection

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

'''

import maya.api.OpenMaya as oMaya
import maya.api.OpenMayaAnim as oAnim
import maya.api.OpenMayaRender as oMayaRender
from string import digits
import os
from maya import cmds
from maya import mel
import re
import inspect

class MayaAsciiParser():	
	objectsImported = list()
	'''
		publicly editable presets
	'''
	nameblacklist = ["persp",
				  "top",
				  "side",
				  "front",
				  'uiConfigurationScriptNode',
				  'layerManager',
				  'renderLayerManager',
				  'defaultRenderLayer',
				  'shapeEditorManager',
				  'lightLinker1'
				  ]		
	nodeblacklist = ['camera',
					'script',
					'shapeEditorManager',
					'nodeGraphEditorInfo',
					'displayLayer',
					'displayLayerManager',
					'defaultResolution',
					'hardwareRenderingGlobals',
					'renderGlobalsList1',				  
					'poseInterpolatorManager',
					'renderLayerManager',
					'renderLayer',
					'aiOptions',
					'aiAOVDriver',
					'aiAOVFilter',
					'aiImagerDenoiserOidn',
					'lightLinker']
	nodeNoDuplicate = ['file','shadingEngine','place2dTexture','place3dTexture']

	connectblacklist = ['defaultRenderLayer']
	
	__namedictionary__ = dict() #name comparitor incase nodes got remapped
	__meshes__ = []
	__shaders__ = []	
	__transforms__ = []

	def __init__(self):
		pass
		
	def getTypeName(self,str):
		'''
			Returns the Node Type of the node.

			@param[in]: Line of maya ascii
			@param[out]: Returns a single string
		'''
		splitstring = str.split('\n')		
		
		splitstring = splitstring[0].split(" ")
		return splitstring[0]
	
	def getNodeParent(self,str):
		'''
			Returns the parent name of a node.

			@param[in]: Line of maya ascii
			@param[out]: Returns a single string
		'''
		splitstring = str.split('\n')	
		
		namefound = splitstring[0]
		if "-p \"" not in namefound and "-parent \"" not in namefound:
			return ""
		start = "-p \""
		if ("-parent \"" in namefound):
			start = "-parent \""
		end = "\""
		startIndex = namefound.find(start)+len(start)
		return namefound[startIndex:namefound.find(end,startIndex) ]
	
	def getNodeName(self,str):
		'''
			Returns the node's name.

			@param[in]: Line of maya ascii
			@param[out]: Returns a single string
		'''
		splitstring = str.split('\n')
		if len(splitstring) == 0:
			return None
		namefound = splitstring[0]
		start = "-n \""
		if ("-name" in namefound):
			start = "-name \""
		end = "\""
		startIndex = namefound.find(start)+len(start)
		return namefound[startIndex:namefound.find(end,startIndex) ]
	
	def filterNodes(self,parsedlist,connectionList):
		'''
			Iterates through every node and sorts out what the nodes that needs to be
			processed.

			@param[in]: Array
			@param[in]: Array of connection commands
			@param[out]: Returns List of meshes
			@param[out]: Returns list of paired shader groups
			@param[out]: Returns skin nodes
			@param[out]: Returns transform nodes
			@param[out]: Returns miscellanous nodes (file nodes texture nodes etc)

		'''
		meshlist = []
		shaders = []
		skinnodes = []
		othernodes = []
		transforms = []
		for i in range(len(parsedlist)):
			if i > 0:				
				nodeType = self.getTypeName(parsedlist[i])
				nodeName = self.getNodeName(parsedlist[i])						
				if (nodeName not in self.nameblacklist) and (nodeType not in self.nodeblacklist):
					if nodeType == 'skinCluster':
						skinnodes.append(parsedlist[i])
						continue
					if nodeType == 'transform':
						transforms.append(parsedlist[i])
					if nodeType == 'mesh':
						# insert createNode string back 					
						transformname = self.getNodeParent(parsedlist[i])												
						meshlist.append(parsedlist[i])
						meshlist.append(transformname)
						continue
					elif nodeType == 'shadingEngine':		
						nodeName = self.getNodeName(parsedlist[i])					
						cons = self.findConnectionsTo(nodeName+".",connectionList)					
						for c in range(len(cons)):
							plugname = self.getPlugName(cons[c][0])
							plugConnectedTo = cons[c][1].split(".")						
							if( plugname == 'surfaceShader' or plugname == 'ss' ):
								# find the shader													
								shaderNode,index = self.findNodeName(parsedlist,plugConnectedTo[0])										
								
						shaders.append( (parsedlist[i],shaderNode) )
					else:
						othernodes.append(parsedlist[i])
					
		return meshlist,shaders,skinnodes,transforms,othernodes
	
	def findNodeName(self,parsedlist,search):
		'''
			Searches for a node based on its name.

			@param[in]: Array of nodes
			@param[in]: Node name to search for
			@param[out]: Returns the whole Node entry (Empty string if not found)
			@param[out]: Returns the array index of the node (-1 if not found)
		'''
		for i in range(len(parsedlist)):
			if i > 0:
				nodeName = self.getNodeName(parsedlist[i])
				if nodeName == search:
					return parsedlist[i],i
		return "",-1
			

	def getAttributeValue(self,line,attributeLabel,end=" "):
		'''
			Returns Attribute value tagged with its label -attributename "attributevalue".

			@param[in]: Line of maya ascii
			@param[in]: Attribute name to retrieve values from , best when paired with self.longOrShortNames() 
			@param[in]: (Optional) Termination string usually a space or a ";"
			@param[out]: Returns the string value of the attribute
		'''
		
		try:			
			startIndex = line.find(attributeLabel)+len(attributeLabel)		
		except:			
			raise Exception("ERROR cant get attribute label "+attributeLabel+" in line "+line)
		return line[startIndex:line.find(end,startIndex)]


	def longOrShortNames(self,line,labels):		
		'''
			Searches for the attribute label based on its alternate names ['-sn','-longname'] and returns the detected
			version of the label.

			@param[in]: Line of maya ascii
			@param[in]: Array string indices of attribute names and their alternates
			@param[in]: Returns the detected label found in the node
		'''
		for l in labels:
			if l in line:
				return l
		return None

	def getEdgeID(self,value):		
		'''
			Determines if the edge is flipped or not and returns the correct edge ID.

			@param[in]: EdgeID
			@param[out]: (int) Returns Real EdgeID
			@param[out]: (boolean) Returns if the edge is flipped
		'''
		flipped = False
		if (value < 0):
			flipped = True
		edgeID = int(value)
		if flipped:
			#https://cgkit.sourceforge.net/doc2/mayaascii.html#polyface
			edgeID = -edgeID-1
		return edgeID,flipped
	

	
	
	def parseMesh(self,maMel):	
		'''
			Parses the Maya ascii node and generates the necessary arrays to build a mesh.

			@param[in]: Line of maya ascii containing a mesh createNode
			@param[out]: Returns mesh DAG Object
			@param[out]: Returns material Face Assignment components
			@param[out]: Returns vertex tweaks in vectors

		'''
		#https://help.autodesk.com/cloudhelp/2025/CHS/Maya-Tech-Docs/CommandsPython/setAttr.html
		#https://help.autodesk.com/view/MAYAUL/2022/ENU/?guid=Maya_SDK_py_ref_class_open_maya_1_1_m_fn_mesh_html		
		faceCount = 0
		edgeCount = 0
		vertCount = 0
		uvnames = []
		uvsets = []
		uvsetsHoles = dict()
		verts = []
		edges = []
		faces = []	
		faceVertexIDs=[]			
		normals = []
		normals2 = []				
		allEdges = []
		allEdgeFaceDesc = []
		allEdgeFaceConnects = []
		allEdgeConnectionCount = []
		allFacesVIDs=[]
		fs = [] # faceIDs
		mus = [] # uvfaces		
		holes = [] # holes		
		colors = dict() # colors		
		vertexIDList = []
		materialFaceAssignment = dict()
		tweaks = []
				
		
		commandlines = maMel.split(";")		
		otherAttribs = []
		for i in range(len(commandlines)):			
			lines = commandlines[i]+";"

			# UV Map Name			
			if('".uvSet' in lines or '".uvst' in lines)  and ('-type "string"' in lines):
				# new UV Map named found								
				UVname = self.getAttributeValue(lines,'-type "string" "','";')
				uvnames.append(UVname)
				continue

			# UV Components
			if ('.uvSetPoints' in lines or '.uvsp' in lines):				
				if '.uvsp";' in lines or '.uvSetPoints";' in lines :
					continue

				if '-type "float2"' in lines:
					uvpoints = self.getAttributeValue(lines,'-type "float2" ',';')					
				else:
					uvpoints = self.getAttributeValue(lines,'" ',';')	
					
				uvpoints = re.sub(r"[\n\t]*", "", uvpoints)	
				if('Attr' in uvpoints):
					raise Exception("Invalid UV return ",lines)
				# if this is a continuation in a segmented list append results ie [0:34] + [35:90]
				if (len(uvnames) == len(uvsets)):
					currentIndex = len(uvsets)-1
					currentlist = uvsets[currentIndex]
					uvsets[currentIndex] = currentlist +" "+ uvpoints										
				else:					
					uvsets.append(uvpoints)		
				continue			

			# Component Tweaks
			if '".pnts' in lines or '".pt' in lines :
				tweaks.append(lines)
				continue

			# Vertex Components
			if '".vrts'	in lines or '".vt' in lines:
				# parse Verts
				try:
					tempC = int( self.getAttributeValue(lines,self.longOrShortNames(lines,["-s ","-size "])))
					vertCount = tempC
				except:
					pass
				if '".vt";' in lines or '".vrts";' in lines:
					#skip this has no entries
					continue
				vertPoints = self.getAttributeValue(lines,'" ',";")
				vertData = re.sub(r"[\n\t]*", "", vertPoints).strip().split(" ")				
				vlen = int(len(vertData)/3)
				
				for v in range(vlen):
					vIndex = len(verts)
					mPoint = oMaya.MPoint()
					mPoint.x = vertData[v*3]
					mPoint.y = vertData[(v*3) + 1]
					mPoint.z = vertData[(v*3) + 2]
					verts.append(mPoint)
					
				continue
					
			
			# Edge Component
			if '".edge' in lines or '".ed' in lines:
				# parse Edges
				try:
					tempC = int(self.getAttributeValue(lines,self.longOrShortNames(lines,["-s ","-size "])))
					edgeCount = tempC					
				except:
					pass
				if '".ed";' in lines or '".edge";'in lines:
					# empty
					continue
				edgesraw = self.getAttributeValue(lines,']" ',";")				
				edgesraw = list(map( int, re.sub(r"[\n\t]*", "", edgesraw).strip().split(" ")))
				#tokenize edges				
				edgeLen = int(len(edgesraw)/3)
				
				dv = int(len(edgesraw) / edgeLen)				
				for ei in range(edgeLen):
					edges.append(edgesraw[ei*dv:(ei*dv)+dv])
				continue

			# Face Component
			if  '".face' in lines or '".fc' in lines:						
				# parse Faces				
				try:
					tempC = int(self.getAttributeValue(lines,self.longOrShortNames(lines,["-s ","-size "])))	
					faceCount = tempC
				except:
					pass
				if '".face";' in lines or '".fc";' in lines:
					# empty
					continue
				
				facesData = self.getAttributeValue(lines,'-type "polyFaces" ',";").strip()									
				faces =  re.sub(r"[\t]*", "", facesData).strip().split("\n")				
				# get face components 
				currentMode = "f"
				currentModeB = "f"
				findex = 0
				mindex = 0
				hindex = 0
				cindex = 0
				for ff in faces:	
						
					if 'mc'	in ff:
						currentMode = 'mc'
						# add face index where this thing lines up with
						carray = list(map(int,ff.split(" ")[1:]))								
						try:
							colors[findex].append(carray)
						except:
							colors[findex] = [carray]
						
					elif 'h' in ff:
						# Faces can have multiple holes						
						currentMode = 'h'
						currentModeB = currentMode
						# add face index where this thing lines up with

						harray = [findex]+list(map(int,ff.split(" ")[2:]))						
						hindex = len(holes)
						holes.append(harray)

						
					elif 'f' in ff:
						currentMode = 'f'	
						currentModeB = currentMode
						fuarray = list(map(int,ff.split(" ")[1:]))
						findex = len(fs)
						fs.append(fuarray)					
						
					elif 'mu' in ff:
						# check if this UV is for a face or a hole.		
						currentMode = 'mu'				
						if currentModeB == 'f':
							muarray = list(map(int,ff.split(" ")[1:]))																				
							mindex = len(mus)
							mus.append(muarray)
						else:							
							# hole , figure out multi uvs 
							muarray = list(map(int,ff.split(" ")[1:]))	
							try:
								uvsetsHoles[findex].append(muarray)
							except:
								uvsetsHoles[findex] = [muarray]						
					
					elif currentMode == 'mc':
						carray = list(map(int,ff.split(" ")[1:]))
						colors[findex][-1] += carray
						
					elif currentMode == 'h':
						harray = list(map(int,ff.split(" ")[1:]))						
						holes[hindex] += harray

						#faceHole[findex] += harray	
						
					elif currentMode == 'f':						
						fuarray = list(map(int,ff.split(" ")[1:]))						
						fs[findex] += fuarray
						
					elif currentMode == "mu":
						if currentModeB == 'f':
							muarray = list(map(int,ff.split(" ")[1:]))						
							mus[mindex] += muarray
						else:
							#todo: holes
							
							muarray = list(map(int,ff.split(" ")[1:]))						
							uvsetsHoles[findex][-1] += muarray
						
							
							
					
				continue

			#	Normals Component
			if '".normals' in lines or '".n' in lines:				
				#normals per face vertex
				try:
					normSize = int(self.getAttributeValue(lines,self.longOrShortNames(lines,["-s ","-size "])))	
				except:
					pass				
				if '".normals";' in lines or '".n";' in lines:
					continue
				normalData = self.getAttributeValue(lines,'-type "float3" ',";").strip()	
				try:							
					normalData = list(map( float, re.sub(r"[\n\t]*", "", normalData).split(' ')))					
				except Exception as e:
					raise Exception("problem parsing normal data ",lines)
				normSize = int(len(normalData)/3)
				for n in range(normSize):					
					vNormal = oMaya.MVector()
					vNormal.x = normalData[ 0 + (n*3) ]
					vNormal.y = normalData[ 1 + (n*3) ]
					vNormal.z = normalData[ 2 + (n*3) ]
					normals.append(vNormal)
					normals2.append( [vNormal.x,vNormal.y,vNormal.z] )
				continue

			# 	Material Assignments
			if ('".instObjGroups[0].objectGroups";' in lines or  '".iog[0].og";' in lines):
				continue
			elif ('".instObjGroups[0].objectGroups' in lines or '".iog[0].og' in lines):
				materialData = self.getAttributeValue(lines,'-type "componentList"',';').strip()
				#materialData = re.sub(r"[\n\tf\[\]\"]*", "", materialData) # convert "[32:50]" to 32:50
				materialData = re.sub(r"[\n\t\"]*", "", materialData) # convert "[32:50]" to 32:50
				materialData = materialData.split(" ")
				materialFaceSize = int(materialData.pop(0))
				
				materialIndex = 0
				if '".instObjGroups[0].objectGroups' in lines:
					materialIndex = int(self.getAttributeValue(lines,'.instObjGroups[0].objectGroups[','].objectGrpCompList"'))
				else:
					materialIndex = int(self.getAttributeValue(lines,'.iog[0].og[','].gcl"'))				
				materialFaceAssignment[materialIndex] = materialData
				continue

			#everything else goes here
			if i == 0:
				meshparent = self.getNodeParent(lines)
			if i > 0 and 'rename ' not in lines:			
				otherAttribs.append(lines)

		for e in range(edgeCount):			
			allEdges = allEdges + edges[e][0:2]							

		
		if faceCount == 0:
			faceCount = len(fs)				

		for f in range(faceCount):						
			fd = fs[f]# fs[f].split(" ")
			pcount = fd[0]#int(fd[1])									
			faceVIDs = [0] * pcount
			edgeIDList = []
			
					
			for eid in range(pcount):	
							
				edgeID,flipped = self.getEdgeID(fd[1+eid])				
				
				if flipped:					
					faceVIDs[eid] = int(edges[edgeID][1])
					allEdgeFaceDesc.append(1) 					
				else:
					faceVIDs[eid] = int(edges[edgeID][0])
					allEdgeFaceDesc.append(0) 				
				edgeIDList.append(edgeID)

			hcount = 0	
			
			allEdgeConnectionCount.append(pcount+hcount)	
			allFacesVIDs = allFacesVIDs + faceVIDs
			faceVertexIDs.append(faceVIDs)
			allEdgeFaceConnects = allEdgeFaceConnects + edgeIDList
					
		'''	
		Create mesh node		
		'''				
		#https://help.autodesk.com/view/MAYAUL/2023/ENU/?guid=MAYA_API_REF_cpp_ref_class_m_fn_mesh_html		
		mesh = oMaya.MFnMesh()		
		parent = None
		# assigning parent object fails.				
		for t in self.__transforms__:
				parentName,groupOBJ = t				
				if(parentName == meshparent):					
					parent = groupOBJ
		
		mesh.create( verts , allEdges , allEdgeConnectionCount , allEdgeFaceConnects , allEdgeFaceDesc,  parent=parent.object())		
		
		#add holes
		for h in range(len(holes)):
			holeEdges = holes[h]
			
			faceID = -1
			vertexlist = []#set()
			for e in range(len(holeEdges)):
				if e == 0:					
					faceID = holeEdges[e]
					
					
				if e > 0 :
					edgeID,flipped = self.getEdgeID(holeEdges[e])					
					if flipped:
						vertexlist.append(edges[edgeID][1])										
					else:
						vertexlist.append(edges[edgeID][0])				
						
									
			#vertexlist = list(vertexlist)
			points = []
			for v in range(len(vertexlist)):				
				points.append(verts[vertexlist[v]])
									
			mesh.addHoles(faceID,points,[len(points)],False)						
		
		uvmapcount = len(uvnames)
		for uvn in range(uvmapcount):
			#print("Attempting UV maps ",uvmapcount," ",uvnames[uvn])
			if uvnames[uvn] != "map1":
				mesh.createUVSet(uvnames[uvn])		
			uvw = []
			uvv = []
			uvsize=[]
			
			if uvn >= len(uvsets):
				if (len(uvsets) == 0):
					continue
				
				uvsets[uvn] = uvsets[uvn].strip();											
				#print("WARNING this mesh may have construction history. missing UV assignments")
				continue
			else:				
				uvpoints = list(map(float, uvsets[uvn].split(" ") ))
				uvcount = int(len(uvpoints)/2)
				for uvp in range(uvcount):				
					u = uvpoints[0 + (uvp * 2) ]
					v = uvpoints[1 + (uvp * 2) ]				
					uvw.append(u)
					uvv.append(v)				
				uvids = []
				faceID = 0
				for m in range(len(mus)):									
					muis = mus[m]					
					if muis[0] == uvn:	
						vcount = muis[1]					
						uvsize.append(vcount)																				
						uvids += muis[2:]	
						
						try:
							#handles multiple holes per face
							holeFaceUV = uvsetsHoles[faceID]
							for hUV in range(len(holeFaceUV)):
								if holeFaceUV[hUV][0] == uvn:									
									uvsize[-1] = uvsize[-1] + holeFaceUV[hUV][1]						
									uvids += holeFaceUV[hUV][2:]
						except:
							pass
						
						faceID += 1

				# // Todo add holes in UV
				mesh.setUVs(uvw,uvv,uvnames[uvn])	

				try:								
					mesh.assignUVs(uvsize,uvids,uvnames[uvn])	
				except:
					print("Unable to assign UVs to  ",mesh.partialPathName(),uvnames[uvn])

		# if normals counts equal to vertex count it means per vertex normals
		if len(normals) == vertCount:
			for aindex in range(len(normals)):
				vertexIDList.append(aindex)
			mesh.setVertexNormals(normals,vertexIDList)
			
		else:
			if len(normals) > 0:			
				allNormals = oMaya.MVectorArray(normals)						
				#condense the perFace vertex normals to a per Vertex shared normals.			
				allFacesVIDs = oMaya.MIntArray(allFacesVIDs)
				# this doesn't work.  setFaceVertexNormals is bugged
				#
				# mesh.setFaceVertexNormals(allNormals,allFaceIDs,allFacesVIDs)		
				#
				# this is the work around to do it per vertex
				#
				vertNormals = []
				for aindex in range(len(allFacesVIDs)):
					vindex = allFacesVIDs[aindex]	
					try:
						vertNormals.append(allNormals[aindex])
						vertexIDList.append(vindex)	
					except:
						pass
						
				mesh.setVertexNormals(vertNormals,vertexIDList)
					
			
					
			
						
		# Edge Normals
		for eid in range(edgeCount):		
			edgeSmooth = False
			if int(edges[eid][2]) == 1:
				edgeSmooth = True	
			mesh.setEdgeSmoothing(eid,edgeSmooth)					
		mesh.cleanupEdgeSmoothing()		
		mesh.updateSurface()		
		meshName = mesh.name()
		colorDictionary = dict()
		
		for m in range(len(otherAttribs)):
			refabstring = otherAttribs[m].replace('".', '"{0}.'.format(meshName)).strip()	
			refabstring = re.sub(r"[\n\t;]*", "", refabstring)
			if ('.colorName' in refabstring  and '.colorSet' in refabstring) or ('.clsn'in refabstring and '.clst' in refabstring):
				colorName = self.getAttributeValue(refabstring,'-type "string" "',';')
				if '.colorName' in refabstring:
					colorSetIndex = int(self.getAttributeValue(refabstring,'.colorSet[','].colorName"'))				
				else:
					colorSetIndex = int(self.getAttributeValue(refabstring,'.clst[','].clsn"'))						
				if colorSetIndex not in colorDictionary.keys():
					colorDictionary[colorSetIndex] = [colorName,4,list(),oMaya.MColorArray(),list(),list()] # 4 channels , ColorPoints, Output Colors, OutputFaceIDs , OutputVertexIDs
			if ('.colorSet' in refabstring and '.representation' in refabstring) or ('.clst' in refabstring and '.rprt' in refabstring):
				if 'representation' in refabstring:
					colorSetIndex = int(self.getAttributeValue(refabstring,'.colorSet[','].representation'))
					colorRep = self.getAttributeValue(refabstring+";",'].representation" ',";")
				else:
					colorSetIndex = int(self.getAttributeValue(refabstring,'.clst[','].rprt'))
					colorRep = self.getAttributeValue(refabstring+";",'].rprt" ',";")
				
				try:					
					colorDictionary[colorSetIndex][1] = int(colorRep)
				except:
					# sometimes if there is a construction history for the color set the representation becomes a place holder.
					pass
			elif ('.colorSetPoints' in refabstring) or ('.clsp' in refabstring):
				refab = refabstring+";"
				if ('.clsp";' in refab) or ('.colorSetPoints";' in refab):							
					continue

				if '.colorSetPoints' in refabstring:
					colorSetIndex = int(self.getAttributeValue(refabstring,'.colorSet[','].colorSetPoints'))
				else:
					colorSetIndex = int(self.getAttributeValue(refabstring,'.clst[','].clsp'))

				colorValues = self.getAttributeValue(refabstring+";",']" ',"; ").split(" ")
				colorValues = list(filter(None, colorValues))
				#tokenize array of numbers				
				colorDictionary[colorSetIndex][2] += colorValues; #colorLists
				

			try:
				mel.eval(refabstring)
			except Exception as e:
				print("Cant set attribute ",refabstring)
				print(e)				
				#raise Exception("Error mesh attrib",refabstring)

		# Color sets	
		defaultColor = mesh.currentColorSetName()
		colorSetPoints = 2		
		outputColors = 3
		outputColorFaces = 4
		outputColorVertexes = 5
		#tokenize values
		for colorSetIndex,value in colorDictionary.items():
			colorValues = colorDictionary[colorSetIndex][2]
			colorRep = colorDictionary[colorSetIndex][1]
			colorIndexes = int(len(colorValues) / colorRep)
			colorLists = []
			
			for c in range(colorIndexes):
				mColor = oMaya.MColor()
				mColor.r = float(colorValues[ (c * colorRep) + 0 ])
				mColor.g = float(colorValues[ (c * colorRep) + 1 ])
				mColor.b = float(colorValues[ (c * colorRep) + 2 ])
				if colorRep > 3:
					mColor.a = float(colorValues[ (c * colorRep) + 3 ])					
				colorLists.append(mColor)
			colorDictionary[colorSetIndex][2] = colorLists

		for faceID,value in colors.items():					
			faceColors = value			
			vertexIDs = faceVertexIDs[faceID]	
			for fc in range(len(faceColors)):
				colorSetIndex = int(faceColors[fc][0])
				colorCount = faceColors[fc][1]
				colorItems = faceColors[fc][2:]		
				
				for fi in range(len(colorItems)):
					vertID = vertexIDs[fi]	
					
					if colorItems[fi] != -1:						
						mColor = colorDictionary[colorSetIndex][colorSetPoints][ colorItems[fi] ] 						
						colorDictionary[colorSetIndex][outputColors].append(mColor)
						colorDictionary[colorSetIndex][outputColorVertexes].append(vertID)				
						colorDictionary[colorSetIndex][outputColorFaces].append(faceID)							

		for colorSetIndex,value in colorDictionary.items():					
			mesh.setCurrentColorSetName( colorDictionary[colorSetIndex][0])					
			mesh.clearColors()
			
			if len(colorDictionary[colorSetIndex][outputColors]) > 0:				
				mesh.setFaceVertexColors( 
					colorDictionary[colorSetIndex][outputColors], 
					colorDictionary[colorSetIndex][outputColorFaces],
					colorDictionary[colorSetIndex][outputColorVertexes])
			mesh.updateSurface()
		
		try:
			mesh.setCurrentColorSetName( defaultColor )		
		except:
			pass
				

		return mesh, materialFaceAssignment, tweaks
	

	def createTransformNodes(self,parsedList):
		'''

			Instantiates Transform nodes from a list of tranform nodes. Any nodes that generates a new name will update
			a name dictionary for later connection redirects.

			@param[in]: Array of Create Nodes
			
		'''
		for i in range(len(parsedList)):
			transformData = parsedList[i]
			nodeName = self.getNodeName(transformData)
			lines = transformData.split(";")
			resultname = nodeName
			for l in range(len(lines)):
				line = lines[l]
				if 'rename ' not in line:
					if l == 0 :
						#filter renamed entities
						newName = self.incrimentNodeName(nodeName)
						self.__namedictionary__[nodeName] = newName
						line = self.retargetRenamedEntities(line)
						resultname = mel.eval("createNode "+line)												
						mSel = oMaya.MSelectionList()
						mSel.add(resultname)
						parentOBJ = mSel.getComponent(0)
						parentOBJ = oMaya.MFnTransform(parentOBJ[0])							
						
						self.__transforms__.append( (nodeName,parentOBJ))												
					else:
						if 'setAttr' in line:
							attrib = line.split(" ")
						refabstring = line.replace('".', '"{0}.'.format(resultname))
						mel.eval(refabstring)

	
	def connectMeshToMaterial(self,mesh,shaderGroup="initialShadingGroup",faceset=[]):
		'''
			Connects the Mesh and its faces to its designated materials.

			@param[in]: Mesh DAG Node
			@param[in]: Shader Group name
			@param[in]: Array of mesh face components in maya's component format ie "shapenodeName.f[0:23]"
		'''
		shadersel = oMaya.MSelectionList()
		shadersel.add(shaderGroup)		
		mshadingGroup = shadersel.getDependNode(0)
		print("shading group",shaderGroup)		
		setFn = oMaya.MFnSet(mshadingGroup)				
		mshadersel = oMaya.MSelectionList()		
		if len(faceset) == 0:
			mshadersel.add(mesh.fullPathName())						
		else:			
			for f in range(len(faceset)):			
				fs = mesh.name()+"."+faceset[f]									
				mshadersel.add( fs )
		try:
			setFn.addMembers( mshadersel )
		except:
			print(" unable to apply face materials to ",mesh.name()," shaderGroup ",shaderGroup," faces ",faceset)
		


	def incrimentNodeName(self,name):
		'''
			Takes a Node name and add an incriment prefix if its not unique.
		
			@param[in]: Node name to make Unique
			@param[out]: Returns a string of a new Unique name
		'''
		if cmds.objExists(name):							
				meshName = name.rstrip(digits)
				incs = 1;
				newMeshName = meshName+str(incs)
				while cmds.objExists( newMeshName ):					
					incs += 1
					newMeshName = meshName+str(incs)
				return newMeshName
		else:
			return name
		


	def getPlugName(self,str):
		'''
			Returns the connecting attribute name.

			@param[in]: dag and plug path  "mynode.attributeplug"
			@param[out]: Returns the plug name  "attributeplug"
		'''
		plugpaths = str.split(".")
		return plugpaths[1]
	


	def createMeshNodes(self,parsedlist):
		'''
			Iterates througha list of mesh create nodes and create the mesh nodes and sort them into a list.
			
			@param[in]: Array of Mesh Nodes in maya Ascii createnodes			
		'''
		ms = []		
		
		for i in range(0,len(parsedlist),2):
			meshName = self.getNodeName(parsedlist[i])						
			parentName = parsedlist[i+1]								
			oldMeshName = meshName			
			meshOBJ,faceMaterial,vertextweaks = self.parseMesh(parsedlist[i] )												
			self.__meshes__.append( (oldMeshName,meshOBJ,faceMaterial,parentName,vertextweaks) )
			if cmds.objExists(meshName):							
				meshName = meshName.rstrip(digits)
				meshName+="#"
			meshOBJ.setName(meshName)
			meshName = meshOBJ.name()
			self.__namedictionary__[oldMeshName] = meshName
			ms.append(meshOBJ.fullPathName())			
			

	def applyVertexTweaks(self):
		'''
			Apply vertex position tweaks to each mesh registered in __meshes__
			This is done after the create nodes are parsed and processed.
		'''
		for mesh in self.__meshes__:
			meshOBJ = mesh[1]
			tweaks = mesh[4]	
			meshname = meshOBJ.name()		
			refabstring = ""				
			for line in tweaks:
				refabstring += line.replace('".', '"{0}.'.format(meshname)).strip()+"\n"
			mel.eval(refabstring)
			
			
	
	def createShaderNodes(self,parsedlist):
		'''
			Instantiate shaders and its shader group pair.
		
			@param[in]: Array of Shader Groups and Shaders to instantiate
		'''
		#use  self.namedictionary to keep track of name changes
		for i in range(len(parsedlist)):			
			shaderGroupRaw = parsedlist[i][0]
			shaderRaw = parsedlist[i][1]
			shaderGroupName = self.getNodeName(shaderGroupRaw)
			shaderName = self.getNodeName(shaderRaw)
			shaderType = self.getTypeName(shaderRaw)
			print("Creating ",shaderGroupName,shaderName,shaderType)
			if(shaderName == ""):
				raise Exception("WTF not a valid shader",parsedlist[i])
			material = cmds.shadingNode(shaderType, name=shaderName, asShader=True)			
			sg = cmds.sets(name=shaderGroupName,empty=True,renderable=True,noSurfaceShader=True)		
			cmds.connectAttr("%s.outColor" % material, "%s.surfaceShader" % sg)			
			shaderValues = re.sub(r"[\n\t]*","", shaderRaw).strip().split(";")			
			for s in range(len(shaderValues)):
				if 'setAttr' in shaderValues[s]:
					attrib = shaderValues[s].split(" ")
					refabstring = shaderValues[s].replace('".', '"{0}.'.format(shaderName))
					try:					
						mel.eval(refabstring)
					except:
						print("Unable to set attribute ",refabstring)
			self.__shaders__.append((shaderGroupName,shaderName,shaderType))

		
	#https://forum.highend3d.com/t/create-node-in-api/38810
	#connection centric.		
	def makeConnections(self,connections):
		'''
		
			Parse the array connections and connect the nodes

			@param[in]: Array of Connection nodes in maya ascii format

		'''
		successConnections = []
		for c in range(len(connections)):
			con = connections[c].split(" ")
			skip = False
			for m in range(len(self.__meshes__)):
				meshEntry = self.__meshes__[m]
				oldMeshName = meshEntry[0]
				meshOBJ = meshEntry[1]
				faceMaterials = meshEntry[2]
				if( oldMeshName+"." in con[0]):					
					matIndex = -1
					#this is a material assignment to our faces
					if '.instObjGroups.objectGroups[' in con[0]:																		
						matIndex = int(self.getAttributeValue(con[0],'.instObjGroups.objectGroups[',']'))
					elif '.iog.og[' in con[0]:						
						matIndex = int(self.getAttributeValue(con[0],'.iog.og[',']'))
						
					if matIndex == -1:
						continue	

					connectionname = re.sub(r"[:]*", "", con[1].split(".")[0] )
					connectedSG = self.__namedictionary__[ connectionname ]							
					if matIndex > -1:									
						self.connectMeshToMaterial(meshOBJ,connectedSG,faceMaterials[matIndex])						
					else:
						self.connectMeshToMaterial(meshOBJ,connectedSG,[])
					skip = True
			#skip = True
			if skip == False:
				
				connections[c] = self.retargetRenamedEntities(connections[c])
				connectinstring = re.sub(r"[:]*", "", connections[c])					

				cons = connectinstring.split(" ")
				sideA = cons[0].split(".")[0]
				sideA_node = cons[0].split(".")[1]
				sideB = cons[1].split(".")[0]
				if ":default" not in con[0] and sideA not in self.connectblacklist:
					
					if cmds.objExists(sideA) and cmds.objExists(sideB):						
						if cmds.isConnected(cons[0],cons[1]) == False:
							result = None
							# exceptions goes here
							if sideA_node == 'midLayerParent':
								continue
							if sideA == 'shapeEditorManager':								
								continue
								
							
							try:
								result = mel.eval("connectAttr "+connections[c])
								successConnections.append(connections[c])								
								#print("Connecting Success ",connections[c],":",result)
							except:								
								#print("Error executing ",connections[c],"::",cmds.isConnected(cons[0],cons[1]), sideA , sideB )
								pass
					else:
						if cmds.objExists(sideA) == False:
							print("Can't find connections for ",sideA)
						if cmds.objExists(sideB) == False:
							print("Can't find connections for ",sideB)

		return successConnections
	

	def getAllConnectAttr(self,maMel):
		'''
			Formats the connection entry

			@param[in]: Connection node in maya ascii format
			@param[out]: Returns Array of the constituant parts of the connection with out quotes
		'''
		lines = maMel.split(";")
		results = []
		for line in lines:
			if "connectAttr" in line:
				connectString = line.split("connectAttr")[-1].strip()
				connectString = re.sub(r"[\n\t\"]*", "", connectString)
				results.append( connectString )
		return results
	

	def findConnectionsTo(self,sourceName,connectionList,exact=False):
		'''
			Find A connection either from the left or right side of the connection list.

			@param[in]: Source name
			@param[in]: Array of Connection list nodes in maya ascii format
			@param[in]: (Optional) Use Exact matches
			@param[out]: Returns Array of results
		'''
		results = []
		for con in connectionList:
			if sourceName in con:
				connections = con.strip().split(" ")
				conPointA = -1
				conPointB = -1
				connectionFormatted = []
				# format the result to a (Source)Left to Right(Target)
				if exact:
					for a in range(len(connections)):
						if sourceName == connections[a]:						
							conPointA = a
							connectionFormatted.append(connections[a])
							break
					for b in range(len(connections)):
						if sourceName != connections[b]:
							conPointB = b
							connectionFormatted.append(connections[b])
							break
				else:
					for a in range(len(connections)):
						if sourceName in connections[a]:						
							conPointA = a
							connectionFormatted.append(connections[a])
							break
					for b in range(len(connections)):
						if sourceName not in connections[b]:
							conPointB = b
							connectionFormatted.append(connections[b])
							break
				if conPointA !=-1 and conPointB != -1:
					results.append(connectionFormatted)
		return results

	def findExistingShaders(self,shaderlist):
		'''
			Filters out already existing shaders from the list 
		
			@param[in]: Array of shaders parsed from the maya file
			@param[out]: Return array of cleared Shaders that have no duplicates or existing shaders
			@param[out]: Return array of clashing Shaders that already exists
		'''	
		notFoundList = []
		alreadyExists = []
		for s in shaderlist:						
			shaderGroupName = self.getNodeName(s[0])			
			shaderName = self.getNodeName(s[1])			
			print("Looking for ",shaderGroupName,shaderName)			
			self.__namedictionary__[shaderGroupName] = shaderGroupName
			self.__namedictionary__[shaderName] = shaderName
			shaderType = self.getTypeName(s[1])		
			if shaderName == "":
				if cmds.objExists(shaderGroupName):
					alreadyExists.append( (shaderGroupName,shaderName,shaderType) )
			elif cmds.objExists( shaderGroupName )  and cmds.objExists( shaderName ) and cmds.objectType( shaderGroupName ) == "shadingEngine" and cmds.objectType( shaderName) == shaderType:				
				alreadyExists.append( (shaderGroupName,shaderName,shaderType) )
			else:				
				notFoundList.append(s)
			
		return notFoundList,alreadyExists


	def retargetRenamedEntities(self,strings):		
		'''

			Retarget connections to the newly renamed nodes

			@param[in]: Line of maya ascii nodes to retarget
			@param[out]: Returns the string of filtered and redirected nodes
		'''
		strings = strings.split(" ")
		for a in range(len(strings)):
			if '"' in strings[a] :
				quoteds = re.findall('"([^"]*)"', strings[a])
				quoteds = quoteds[0].split(".") # only one quoted string per entry anyways
				for q in range(len(quoteds)):
					for i, key in enumerate(self.__namedictionary__):
						if self.__namedictionary__[key] != key and  key == quoteds[q]:
							quoteds[q] = self.__namedictionary__[key]
				strings[a] = '"'+ ".".join(quoteds) + '"'
			else:
				subattributes = strings[a].split(".")
				for q in range(len(subattributes)):
					for i, key in enumerate(self.__namedictionary__):
						if self.__namedictionary__[key] != key and  key == subattributes[q]:
							subattributes[q] = self.__namedictionary__[key]
							#print("old name found in connection ",key," converting to ",self.__namedictionary__[key], strings)
				strings[a] = ".".join(subattributes)		
		return " ".join(strings)

	

	
	def createOtherNodes(self,otherlist,exception):
		'''
			For other nodes not exclussively filtered this will attempt to instantiate them. If any of these
			return a warning it may mean the nodes are using attributes that can only be used during I/O scene loading

			@param[in]: Array of maya ascii nodes to instantiate that were not picked up by the filters
			@param[in]: Array of node names to ignore
			@param[out]: Returns Array DAG Nodes of successfully created nodes
			@param[out]: Returns Array of created Blend Shape nodes
		'''
		otherNodes = []
		blendshapes = []
		for o in range(len(otherlist)):
			nodeType = self.getTypeName(otherlist[o])
			nodeName = self.getNodeName(otherlist[o])
			#filter out shaders and shape transforms
			skip = False			
			if cmds.objExists(nodeName) and nodeType in self.nodeNoDuplicate:
				continue
			if nodeType in exception:
				continue
			for s in range(len(self.__shaders__)):
				if nodeType == self.__shaders__[s][2]:
					skip = True
				if nodeName == self.__shaders__[s][0]:
					skip = True
			for t in range(len(self.__transforms__)):
				if nodeName == self.__transforms__[t][0]:
					skip = True
			
			if nodeType == 'skinCluster':
				skip = True
			
			if skip:
				continue
			# Skinning
			
				
			# Remove -rename -r 
			lines = otherlist[o].split(";") #otherlist[o].splitlines()
			filtered = []
			resultname = nodeName
			for l in range(len(lines)):				
				line = lines[l]
				if 'rename ' not in line:
					#find self reference  ' ".  ' and replace with node name					
					if l == 0 :
						#filter renamed entities						
						newName = self.incrimentNodeName(nodeName)						
						self.__namedictionary__[nodeName] = newName
						line = self.retargetRenamedEntities(line)																													
						resultname = mel.eval("createNode "+line)												

						#print(nodeType," Creating node ",nodeName," -> ",resultname)
						if resultname != newName:
							raise Exception("New Name didn't match the desired name {0}->{1}".format(newName,resultname))
						if nodeType == "blendShape":
							blendshapes.append( (nodeName,resultname))
						otherNodes.append(resultname)
						
					else:
						#setAttribs
						refabstring = line.replace('".', '"{0}.'.format(resultname))

						# Blend Shape exceptions
						if(('-shortName' in line and '-longName' in line) or ('-sn' in line and '-ln' in line)):							
							shortname = self.getAttributeValue(line,self.longOrShortNames(line,["-sn ","-shortName "]) )
							longname = self.getAttributeValue(line,self.longOrShortNames(line,["-ln ","-longName "]) )							
							if shortname == '"aal"' and longname == '"attributeAliasList"':
								# reserved attributes created at I/O time
								continue	
							
							
						if nodeType == "blendShape":							
							if '".aal"' in line or '".attributeAliasList"' in line:
								#Blend Shape Aliases
								aliasses = self.getAttributeValue(line,'-type "attributeAlias"',";").replace("weight[", resultname+".weight[")
								aliasses = aliasses.split(" ")[2:]
								resultatt = mel.eval('aliasAttr '+ " ".join(aliasses))								
								continue
						try:
							mel.eval(refabstring)
						except:
							pass
		return otherNodes,blendshapes							
			
	def createSkins(self,skinNodes):
		'''		
			Instantiates a list of Skin deformers and sorts out their weight and influences

			@param[in]: Array of maya ascii skin nodes 
			@param[out]: Array of Skin DAG Nodes

		'''
		skinobjects = []
		for s in range(len(skinNodes)):					
			skinName = ""
			newName = skinName
			skindata = skinNodes[s].split(";")
			weightslist = []
			for l in range(len(skindata)):
				skinaAttrib = skindata[l]+";"
				if l == 0:
					skinName = self.getNodeName(skindata[l])										
					newName = mel.eval("createNode "+skindata[l].strip())
					
					self.__namedictionary__[skinName] = newName
				else:					
					#insert objectName into attributes
					skinaAttrib = skinaAttrib.replace('".', '"{0}.'.format(newName))
					
					if '";' in skinaAttrib:
						continue					
					
					skinaAttrib = re.sub(r"[\t]*", "", skinaAttrib)					
					skinaAttrib = " ".join(skinaAttrib.splitlines())
					
					if '.weightList' in skinaAttrib:
						#copy weights list.
						skinaAttrib = self.getAttributeValue(skinaAttrib,'weights" ',';')							
						weightslist += list(filter(str.strip, skinaAttrib.split(" ") )) 
						
					elif '.wl' in skinaAttrib:						
						#copy weights list.
						skinaAttrib = self.getAttributeValue(skinaAttrib,'w" ',';')	
						weightslist  += list(filter(str.strip, skinaAttrib.split(" ") )) 
					else:
						try:
							mel.eval(skinaAttrib)
						except:							
							pass
			# now parse the weights list																		
			skinobjects.append( (newName,weightslist) )
			
		# return the node for deletion on undo
		return skinobjects
					
	def applyWeightsToSkins(self,skins):
		'''
			This transcribes all the weights and influences of the skin node
		
			@param[in]: Array of containing a tupple for Skin DAG nodes and its weight pairs			
		'''
		for s in range(len(skins)):
			skin = skins[s]
			weightslist = skin[1]
			mSel = oMaya.MSelectionList()
			mSel.add(skin[0])
			skin = oAnim.MFnSkinCluster()			
			skin.setObject(mSel.getDependNode(0))
			influenceCount = []
			influenceIndexes = []
			weights = []
			obj = None
			bindedmeshes = skin.getOutputGeometry()
			for binds in bindedmeshes:
				meshObj = oMaya.MFnMesh(binds)
				#meshObj.setObject(binds)							
				vertIter = oMaya.MItMeshVertex(binds)
				skin_plug = skin.findPlug( "weightList",0 ); 
				vertCount = vertIter.count()				
				vertexID = 0
				#for w in range(len(weightslist)):
				w = 0
				while w < len(weightslist):					
					numInfluence = int(weightslist[w])					
					for i in range(numInfluence):						
						w+=1
						influenceID = int(weightslist[w])
						w+=1
						weight = float(weightslist[w])
						#print (weightslist[w])
						# I figured its   {influence count} {influence index} {weight} {influence index} {weight} {influence index} {weight}					
						skin_plug.elementByLogicalIndex(vertexID).child(0).elementByLogicalIndex(influenceID).setFloat( weight ) 						
					vertexID += 1 
					w += 1
							
		
	def connectBlendShapesToShapeManager(self,blendShapes):
		''''
			Connects the blend shapse to the Shape Manager

			@param[in]: Array of blendshape node names and its DAG nodes
		'''
		outblend = cmds.getAttr('shapeEditorManager.outBlendShapeVisibility',multiIndices=True)
		shapeDirectory = cmds.getAttr('shapeEditorManager.blendShapeDirectory[0].childIndices')
		shapeDirectory = []
		if outblend == None:
			outblend = []
			shapeDirectory = []
		index = 0		
		for b in range(len(blendShapes)):
			while index in outblend:
				index += 1
			outblend.append(index)
			shapeDirectory.append(index)			
			blendshapeName = blendShapes[b][1] # result names
			#cmds.connectAttr( '{0}.midLayerParent'.format(blendshapeName), 'shapeEditorManager.blendShapeParent[{0}]'.format(str(index)) )
			cmds.connectAttr( 'shapeEditorManager.outBlendShapeVisibility[{0}]'.format(str(index)), '{0}.targetDirectory[0].directoryParentVisibility'.format(blendshapeName) )
			cmds.setAttr('shapeEditorManager.blendShapeDirectory[0].childIndices',  shapeDirectory, type='Int32Array')

			
		
	def importFile(self,asciipath):		
		'''
			Initiates the import operation 

			@param[in]: File Path of maya.ma file
			@param[out]: Array of imported Mesh Shape node paths
			@param[out]: Array of imported Transform Paths
			@param[out]: Array of imported Shader Node names
			@param[out]: Array of imported Shader Group names
			@param[out]: Array of imported Connections
		'''
		print("Performing Import ",asciipath)	
		
		self.__meshes__ = []
		self.__transforms__ = []
		self.__shaders__=[]
		self.__namedictionary__ = dict()
		self.__namedictionary__["initialShadingGroup"] = "initialShadingGroup"
		others=[]
		exceptions = []
		file1 = open(asciipath, "r")
		file1strings = file1.read()
		# Remove special characters
		file1strings = re.sub('&lf;', "", file1strings)	
		file1strings = re.sub('&cr;', "", file1strings)			
		

		nodes = file1strings.split("createNode ")				
		connections = self.getAllConnectAttr(file1strings)
		meshlist,shaderlist,skins,transforms,othernodes = self.filterNodes(nodes,connections)				
		shaderlist,shaderAlreadyExists = self.findExistingShaders(shaderlist)					
		self.createTransformNodes(transforms)		
		others,blendshapes = self.createOtherNodes(othernodes,exceptions)	
		self.createMeshNodes(meshlist)		
		self.createShaderNodes(shaderlist)
		skins = self.createSkins(skins)
		
		for ex in shaderlist:
			shaderType = self.getTypeName(ex[1])
			exceptions.append(shaderType)
		for ex in shaderAlreadyExists:
			shaderType = ex[2]
			exceptions.append(shaderType)

			

		for s in range(len(skins)):
			others.append( skins[s][0] )
		connections = self.makeConnections(connections)				
		self.applyVertexTweaks()								
		self.applyWeightsToSkins(skins)					
		self.connectBlendShapesToShapeManager(blendshapes)
		
		ms=[]
		ts=[]		
		sh=[]
		sg=[]
		for m in self.__meshes__:
			ms.append( m[1].name() )
		for t in self.__transforms__:
			ts.append( t[1].fullPathName() )
		for s in self.__shaders__:
			sh.append(s[0])
			sg.append(s[1])	
		
		return ms,ts,sh,sg,others,connections


# Self booting the undo plugin		
filename = inspect.getframeinfo(inspect.currentframe()).filename
path = os.path.dirname(os.path.abspath(filename))				
if(cmds.pluginInfo('MayaAsciiImporter.py',l=True, q=True)):
	#cmds.unloadPlugin('MayaAsciiImporter.py',f=True)						
	pass
else:
	cmds.loadPlugin( os.path.join( path,'MayaAsciiImporter.py') )		