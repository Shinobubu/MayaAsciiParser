import maya.api.OpenMaya as om
from maya import cmds
from maya import mel
import os
import copy
import uuid
import inspect
from importlib import reload
from MayaAsciiParser import MayaAsciiParser
#reload(MayaAsciiParser)



def maya_useNewAPI():
	"""
	The presence of this function tells Maya that the plugin produces, and
	expects to be passed, objects created using the Maya Python API 2.0.
	"""
	pass


_pluginName_ = 'MayaAsciiImporter'
_author_ = 'Xyriz Arceo'
_version_ = '1.45'
_apiVersion_ = 'Any'


# --------------------------------------------------------------------------------
# arguments flags
# --------------------------------------------------------------------------------


instanceFlag = '-f'
instanceLongFlag = "AsciiFile"
# THIS IS BAD CODE. Until I find a way for the undo class to know how to get the
# instance this is a temporary fix
callingModule = None
try:
	callingModule = inspect.currentframe().f_back.f_locals['self']
except:
	pass

# --------------------------------------------------------------------------------

class MayaAsciiImporter(om.MPxCommand):
	_name_ = ""
	__instance = ""    	
	__undoCue = []
	__asciifile=""

	def __init__(self):
		self._name_ = str(uuid.uuid4())
		self.__instance = callingModule
		om.MPxCommand.__init__(self)

	#https://forums.autodesk.com/t5/maya-programming/python-api-2-0-command-plug-in-setresult-always-returns-a-list/td-p/8654475
	def doIt(self, argList):					
		#Due to use of Mel Commands undo info has to be disabled temporarily between functions
		cmds.undoInfo(swf=False)	
		self.__asciifile = argList.asString(0)		
		mayaimporter = MayaAsciiParser.MayaAsciiParser()
		m , t , sh , sg, o, c = mayaimporter.importFile(self.__asciifile)
		self.__undoCue.append( (m,t,sh,sg,o,c) )		
		cmds.undoInfo(swf=True)	
		om.MPxCommand.setResult(m)
		om.MPxCommand.appendToResult(t)		
		return True

	
	
	def redoIt(self):					
		cmds.undoInfo(swf=False)	
		mayaimporter = MayaAsciiParser.MayaAsciiParser()		
		m , t , sh , sg, o, c = mayaimporter.importFile(self.__asciifile)		
		self.__undoCue.append( (m,t,sh,sg,o,c) )		
		cmds.undoInfo(swf=True)	
		om.MPxCommand.setResult(m)
		om.MPxCommand.appendToResult(t)				
		return True
	

	def undoIt(self):		
		cmds.undoInfo(swf=False)									
		currentQue = self.__undoCue.pop()				
		# undo by order of creation in reverse
						
		
		for cons in currentQue[5]:
			try:
				mel.eval("disconnectAttr "+cons)
			except:				
				pass
		
		# Meshes were entirely made with API so best to nuke it		
		msels = om.MSelectionList()
		mselIter = om.MItSelectionList(msels)
		mod = om.MDGModifier()
		for meshe in currentQue[0]:					
			if cmds.objExists(meshe):				
				msels.add(meshe)					
		while not mselIter.isDone():
			mDag,mComp = mselIter.getComponent()
			mod.deleteNode(mDag.node())
			mselIter.next();				
		mod.doIt();

		
		# delete other nodes
		
		for other in currentQue[4]:			
			if cmds.objExists(other):
				mel.eval("delete {0};".format(other))													
			
		
		# delete transforms
		
		
		for transf in reversed(currentQue[1]):
			if cmds.objExists(transf):
				mel.eval("delete {0};".format(transf))				
				#cmds.delete(transf)
				#msels.add(transf)
		

		for sg in currentQue[2]:
			if cmds.objExists(sg):				
				mel.eval("delete {0};".format(sg))	
				#cmds.delete(sg)
		
		for sh in currentQue[3]:
			if cmds.objExists(sh):				
				mel.eval("delete {0};".format(sh))	
				#cmds.delete(sh)
		cmds.undoInfo(swf=True)	
		return True
		



	def isUndoable(self):
		return True

# --------------------------------------------------------------------------------


def cmdCreator():
	return MayaAsciiImporter()


def syntaxCreator():
	syn = om.MSyntax()    
	syn.addFlag(instanceFlag,instanceLongFlag, om.MSyntax.kString )
	return syn


def initializePlugin(obj):    
	plugin = om.MFnPlugin(obj, _author_, _version_, _apiVersion_)
	try:
		print ("Installing command ",_pluginName_," ver ",_version_)
		plugin.registerCommand(_pluginName_, cmdCreator, syntaxCreator)
	except:
		raise RuntimeError ('Failed to register command')


def uninitializePlugin(obj):
	plugin = om.MFnPlugin(obj)
	try:
		plugin.deregisterCommand(_pluginName_)
	except:
		raise RuntimeError ('Failed to unregister command: {0}\n'.format(_pluginName_))


