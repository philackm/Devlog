"""Devlog: Create a static HTML website containing development logs that are
generated from individual markdown files."""

from abc import ABC, abstractmethod # Abstract classes

import os                           # File reading and writing
import shutil                       # File copying
import sys                          # For command line arguments
import argparse                     # For command line arguments.

from datetime import datetime       # Converting dates

import re                           # Regular expressions
from collections import defaultdict # defaultdict, so we can easily store key, value pairs, and if it doesn't exist, have an array ready
import json                         # Parsing and working with JSON 

import urllib.request               # Communicating with Github to render markdown into HTML
import urllib.error                 

# Model: Entry, Template, BuildHistory
# Controller: Devlog, Parser, FileSystem, HTTP
# View: Template 

# TODO:
# Paths
# DONE - Fix build and init paths (simplifying)
# DONE - Fix .buildhistory saving location (it is currently loading from pwd of python)
# DONE - Template view directory doesnt know where to go in template.load, hardcoded devlog

# Meta
# DONE - actual link to page on index
# DONE - Github Links

# Additional Features
# - 'Pinned Projects' & 'All Projects'
# - Youtube embeds


class BuildHistory():
    def __init__(self, rootPath):
        
        self.history = {}

        self.buildHistoryFile = os.path.join(rootPath, ".buildHistory")
        historyLines = FileSystem.readFileIntoLinesArray(self.buildHistoryFile)
        regex = "^(.*)\t(.*)$"
        
        for line in historyLines:
            # Grab the history data in the format: 
            # '<absEntryPath><tab><lastBuildDate>' (without the chevrons).
            match = re.match(regex, line)
            if match:
                key = match.group(1)
                value = match.group(2)
                self.history[key] = value

    def requiresRebuild(self, entry):
        
        lastBuildDate = self.getLastBuildDate(entry)

        if lastBuildDate is None:
            return True
        else:
            # If the last date we have recorded is earlier than the actual 
            # file modification date, should rebuild that entry
            return True if lastBuildDate < entry.lastModificationDate else False

    def getLastBuildDate(self, entry):
        
        absolutePath = os.path.abspath(entry.pathToEntry)

        if absolutePath in self.history:
            dateString = self.history[absolutePath] 
            
            # Format: year-month-day-hour-minute-second
            # All zero padded
            # Hour is 24 hours
            # e.g. 2016-12-15-14-17-32 = 15/12/2016 @ 2:17:32pm
            date = datetime.strptime(dateString, "%Y-%m-%d-%H-%M-%S")
            return date
        else:
            return None

    def update(self, entry):
        
        # Ensure we are using the absolute path to the file.
        # This ensures that we can only ever be talking about a single unique file.
        absolutePath = os.path.abspath(entry.pathToEntry)

        # Update the value in the dict for the key (abspath of the entry) to 
        # the current datetime.
        currentTime = datetime.now()
        currentTimeString = currentTime.strftime("%Y-%m-%d-%H-%M-%S")
        self.history[absolutePath] = currentTimeString
        
        self.__saveHistoryToFile()

    def __saveHistoryToFile(self):
        FileSystem.writeDictIntoFile(self.buildHistoryFile, self.history, "\t")

class Devlog():
    def __init__(self):
        print("Starting devlog...")

        self.rootFolderName = "devlog"
        self.entriesFolderName = "entries"
        self.viewsFolderName = "views"
        self.outputFolderName = "output"

        self.outputPagesFolderName = "pages"
        
        self.pathToEntries = None
        self.pathToViews = None
        self.pathToOutput = None

        self.pathToDevlogRoot = None

    def initialise(self, directoryPath, shouldCreateExampleEntries):
        
        self.pathToDevlogRoot = os.path.join(directoryPath, self.rootFolderName)
        
        self.pathToEntries = os.path.join(self.pathToDevlogRoot, self.entriesFolderName)
        self.pathToViews = os.path.join(self.pathToDevlogRoot, self.viewsFolderName)
        self.pathToOutput = os.path.join(self.pathToDevlogRoot, self.outputFolderName)

        # Need to make sure the directory exists.
        FileSystem.createDirectory(self.pathToDevlogRoot)

        # have to create the intial directories,  entries, views, output folders
        FileSystem.createDirectory(self.pathToEntries)
        FileSystem.createDirectory(self.pathToViews)
        FileSystem.createDirectory(self.pathToOutput)

        # Create a .buildhistory file to keep track of which entries are "out of date".
        try:
            FileSystem.createFile(self.pathToDevlogRoot, ".buildhistory")
        except Exception as e:
            print("Unable to create new devlog directory in directory: {}. A .buildhistory file already exists.".format(self.pathToDevlogRoot))
            print("Are you sure you aren't trying to init in a folder that already contains a devlog?")
            return 

        # Copy across default html views/css/javascript
        defaultAssets = self.__getDefaultViews()

        for path, asset in defaultAssets.items():
            outputPath = os.path.join(self.pathToDevlogRoot, path)
            FileSystem.writeStringIntoFile(outputPath, asset)

        if shouldCreateExampleEntries:                  # TODO
            # If the --examples flag has been passed, then we want to
            # include examples of the different types of entries.
            markdown, binaries = self.__getDefaultEntries()

            for path, asset in markdown.items():
                outputPath = os.path.join(self.pathToDevlogRoot, path)
                FileSystem.writeStringIntoFile(outputPath, asset)

            for path, asset in binaries.items():
                outputPath = os.path.join(self.pathToDevlogRoot, path)
                FileSystem.writeBytesIntoFile(outputPath, asset)
    
    def build(self, location, isIncrementalBuild):

        rootPath = location
        entriesPath = os.path.join(rootPath, self.entriesFolderName)
        viewsPath = os.path.join(rootPath, self.viewsFolderName)
        outputPath = os.path.join(rootPath, self.outputFolderName)

        buildHistory = BuildHistory(rootPath)

        # First get the entire list of entries in the entriesPath
        entries = Entry.entriesInPath(entriesPath, MarkdownEntryParser(), ".md")
        # Maintain another list, the entries that have been updated since the last
        # time we built and therefore require markdown -> HTML generation again.
        entriesToBuild = None

        # If isIncrementalBuild flag is passed we only want to build the entries
        # that have changed rather than building them all.
        if(isIncrementalBuild):
            entriesToBuild = filter(lambda x: buildHistory.requiresRebuild(x), entries)
        else:
            entriesToBuild = entries

        # Generate the HTML for each entry that requires it.
        if entriesToBuild is not None:
            for entry in entriesToBuild:
                # Write out the rendered HTML to its own file
                self.__writePage(outputPath, viewsPath, entry)
                # Move all assets
                pagesDirectory = os.path.join(outputPath, self.outputPagesFolderName)
                FileSystem.copyFiles(entry.assetList, os.path.join(pagesDirectory, entry.fileName))
                # Update the build history.
                buildHistory.update(entry)

        # Generate the main index page, atm, sorted oldest to newest.
        # TODO: Update entry.meta
        sortedEntries = sorted(entries, key=lambda entry: datetime.strptime(entry.meta["date"][0], "%Y-%m-%d"), reverse=False)
        self.__writeIndex(outputPath, viewsPath, sortedEntries)
        
    def __writeIndex(self, outputPath, viewsPath, entries):

        allEntries = str()

        for entry in entries:
            template = Template.load(entry, viewsPath)
            allEntries = "{}{}".format(allEntries, template.render(entry))

        indexOutputFileName = os.path.join(outputPath, "index.html")

        indexTemplatePath = os.path.join(viewsPath, "index.html")
        indexTemplate = FileSystem.readFileIntoString(indexTemplatePath)
        
        regex = "<= entries =>"
        renderedPage = re.sub(regex, allEntries, indexTemplate)
        
        FileSystem.writeStringIntoFile(indexOutputFileName, renderedPage)


    def __writePage(self, outputPath, viewsPath, entry):
        pagesDirectory = os.path.join(outputPath, "pages")
        pageFileName = os.path.join(pagesDirectory, entry.fileName, entry.fileName + ".html")

        pageTemplatePath = os.path.join(viewsPath, "page.html")
        pageTemplate = FileSystem.readFileIntoString(pageTemplatePath)

        regex = "<= entry =>"
        renderedPage = re.sub(regex, entry.generateHTML(), pageTemplate)

        FileSystem.writeStringIntoFile(pageFileName, renderedPage)

    # TODO: Update all of the defaults below.
    # -> [String:String], e.g., [path:string], e.g., ["views/text.html" : "<html>...<html>"]
    def __getDefaultViews(self):

        assets = {}

        # List of default resources needed to create the development log.
        defaults = {
            # needed before build
            # views 
            "views/text.html" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/views/text.html",
            "views/image.html" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/views/image.html",
            "views/video.html" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/views/video.html",
            "views/page.html" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/views/page.html",
            "views/index.html" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/views/index.html",

            # needed after build
            # javascript
            "output/javascript/script.js" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/javascript/script.js",
            # css
            "output/css/page.css" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/css/page.css",
            "output/css/style.css" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/css/style.css"
        }

        # Download, one by one the list of default resources
            # Store them in assets with the key as the location they need to be saved to disk
        for key, value in defaults.items():
            try:
                assets[key] = HTTP.GET(value).decode("utf-8")
            except urllib.error.HTTPError as error:
                print("Unable to locate default resource at URL: {}".format(value))
                print("It has likely been moved or deleted. The build will no longer work correctly.")
        
        return assets

    def __getDefaultEntries(self):

        markdown = {}
        binary = {}

        markdownSource = {
            # Text
            "entries/text/text-1/text-1.md" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/text/text-1/text-1.md",
            "entries/text/text-2/text-2.md" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/text/text-2/text-2.md",
            "entries/text/text-3/text-3.md" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/text/text-3/text-3.md",

            # Images
            "entries/images/image-1/image-1.md" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/images/image-1/image-1.md",
            "entries/images/image-2/image-2.md" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/images/image-2/image-2.md",
            "entries/images/image-2-withtext/image-2-withtext.md" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/images/image-2-withtext/image-2-withtext.md",
            "entries/images/image-3/image-3.md" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/images/image-3/image-3.md",
            "entries/images/image-3-withtext/image-3-withtext.md" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/images/image-3-withtext/image-3-withtext.md"
        }

        binarySource = {
            # Images
            "entries/images/image-1/images/smartphone.jpg" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/images/image-1/images/smartphone.jpg",
            "entries/images/image-2/images/beach.jpg" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/images/image-2/images/beach.jpg",
            "entries/images/image-2-withtext/images/beach.jpg" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/images/image-2-withtext/images/beach.jpg",
            "entries/images/image-3/images/computer.png" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/images/image-3/images/computer.png",
            "entries/images/image-3-withtext/images/computer.png" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/entries/images/image-3-withtext/images/computer.png",

            # Main Index
            "output/assets/user-unknown-icon.jpg" : "https://raw.githubusercontent.com/philackm/Devlog/master/defaults/assets/user-unknown-icon.jpg",
        }

        # Download, one by one the list of markdown files and binaries
        for key, value in markdownSource.items():
            try:
                markdown[key] = HTTP.GET(value).decode("utf-8")
            except urllib.error.HTTPError as error:
                print("Unable to locate default resource at URL: {}".format(value))

        for key, value in binarySource.items():
            try:
                binary[key] = HTTP.GET(value)
            except urllib.error.HTTPError as error:
                print("Unable to locate default resource at URL: {}".format(value))

        return (markdown, binary)

class Entry():
    def __init__(self):
        self.parser = None
        self.pathToEntry = None
        self.fileName = None
        self.lastModificationDate = None
        
        self.meta = None
        self.html = None
        
        self.assetList = None
        
    def generateHTML(self):
        if self.parser:
            return self.parser.generateHTML(self.pathToEntry)
        else:
            return None


    # entriesInPath(Path, EntryParser) -> [Entry]
    @staticmethod
    def entriesInPath(rootPath, parser, filetype):
        paths = FileSystem.findFiles(filetype, rootPath)
        entries = []

        for filePath in paths:
            try:
                entry = Entry()
                entry.parser = parser
                entry.pathToEntry = filePath
                entry.fileName = os.path.basename(filePath).split(".")[0]
                entry.lastModificationDate = datetime.fromtimestamp(os.path.getmtime(entry.pathToEntry))

                # Parse the file and get the metadata and the generated HTML
                entry.meta = parser.parseMeta(filePath)

                # Find any accompanying assets we need to copy for this Entry
                containingDirectory, _ = os.path.split(filePath)
                allowedFileTypes = [".jpg", ".png", ".gif", ".mp4", ".webm", ".mov"] # TODO: pull out into settings file
                entry.assetList = FileSystem.findAnyFiles(allowedFileTypes, containingDirectory)

                entries.append(entry)
            except Exception as e:
                print("Unable to parse file with filename: {}. Skipping...".format(filePath))

        return entries


class Template():
    @staticmethod
    def load(entry, pathToViews):

        kind = str()

        if "video" in entry.meta["kind"]:
            kind = "video"
        elif "image" in entry.meta["kind"]:
            kind = "image"
        else:
            kind = "text"

        viewFileType = ".html"
        viewFile = "{}{}".format(kind, viewFileType)

        templatePath = os.path.join(pathToViews, viewFile)

        return Template(templatePath)

    def __init__(self, templatePath):
        #print("Creating Template")
        self.templatePath = templatePath
        self.templateHTML = FileSystem.readFileIntoString(templatePath)


    def render(self, model):

        renderedHTML = self.templateHTML

        # Data which is processed from meta information in the .md file
        # These are available in the HTML templates using the following keys.
        generatedData = {
            "classes" : self.__generateClasses(model),
            "tags" : self.__generateTags(model),
            "formattedDate" : self.__generateFormattedDate(model),
            "page-link" : self.__generateFullPageLink(model),
            "main-image-link": self.__generareMainImageLink(model)
        }

        for key in generatedData:
            regex = "<= " + key + " =>"
            renderedHTML = re.sub(regex, str(generatedData[key]), renderedHTML)

        # Data which comes directly from the .md file un-edited.
        for key in model.meta:
            value = str(model.meta[key][0])
            regex = "<= " + key + " =>"
            renderedHTML = re.sub(regex, value, renderedHTML)

        return renderedHTML
    
    def __generateClasses(self, model): # -> [String]

        classes = [];
		
        # Added the classes for the kind of entry
        for kind in model.meta["kind"]:
            # The CSS uses the class "withtext" when it is a dual entry type.
            if kind == "text" and len(model.meta["kind"]) >= 2:
                classes.append("withtext")
            else:
                classes.append(kind)
		
        # How many columns does it span
        columns = "col-" + model.meta["columns"][0]
        classes.append(columns)
		
        # Dark or light UI?
        if ("video" in model.meta["kind"] or "image" in model.meta["kind"]) and "text" not in model.meta["kind"]:
            if model.meta["ui"][0] == "light":
                classes.append("lightui")
            else:
                classes.append("darkui")

        return " ".join(classes)

    def __generateTags(self, model): # -> String

        tags = str()

        for tag in model.meta["tag"]:
            tagSpanElement = "<span class=\"tag " + tag.lower() + "\">" + tag + "</span> "
            tags = "{}{}".format(tags, tagSpanElement)
        
        return tags

    def __generateFormattedDate(self, model):
        return datetime.strptime(model.meta["date"][0], "%Y-%m-%d").strftime("%B %Y")
    def __generateFullPageLink(self, model):
        return "pages" + "/" + model.fileName + "/" + model.fileName + ".html"
    def __generateMainImageLink(self, model):
        mainImageLink = str()

        if "main-image" in model.meta:
            relativeImageLocation = model.meta["main-image"][0]
            mainImageLink = "pages/{}/{}".format(model.fileName, relativeImageLocation)
        
        return mainImageLink
    def __generateYouTube(self, model):
        print("todo: __generateYouTube")

class MarkdownEntryParser():
    # parseMeta(entryFilePath) -> {String:String}
    def parseMeta(self, entryFileLocation):
        return self.__genMetaDictionary(entryFileLocation)

    # generateHTML(entryFilePath) -> String
    def generateHTML(self, entryFileLocation):
        return self.__toHTML(entryFileLocation)

    # toHTML(Entry) -> String
    def __toHTML(self, entryFileLocation):

        markdown = FileSystem.readFileIntoString(entryFileLocation)
        
        markdownCompilerURL = "https://api.github.com/markdown"
        data = {"text": markdown, "mode": "markdown", "context": ""}
        headers = {"Content-Type": "application/json"}
        
        # Request Github to compile the markdown into HTML for us.
        return HTTP.POST(markdownCompilerURL, data, headers).decode("utf-8")

    # genMetaDictionary(entryFilePath) -> {String : String}
    def __genMetaDictionary(self, entryFileLocation):

        meta = defaultdict(list)
        lines = FileSystem.readFileIntoLinesArray(entryFileLocation)
        
        for line in lines:
            # Grab the meta data in the format: '[tag]: # (value)'
            match = re.match("^\[(.*)\]:\s#\s\((.*)\)", line)
            if match:
                key = match.group(1)
                value = match.group(2)				
                meta[str(key)].append(value)

            # Grab the path for the entry's main image. '!*(image-path)'
            # TODO: Make this only match the image with the tag "main-image"
            # TODO: Store into its own main-image metadata property
            match = re.match("^!.*\((.*)\)", line)
            if match:
                image = match.group(1)
                meta["main-image"].append(image)

        return meta

# Helper class: Blocking HTTP GET and POST methods.
class HTTP:
    # urllib (request.urlopen) notes:
    # if data is None, then the HTTP method is GET, if some data is passed, then
    # the HTTP method is POST
    @staticmethod
    def GET(url, jsonData = None, headers = {}):

        urlArguments = HTTP.__convertDataForMethod(jsonData, "get")
        
        # Only add the arguments to the end of the URL if we have some data 
        if urlArguments is not None:
            url = "{}?{}".format(url, urlArguments)

        httpRequest = urllib.request.Request(url, None, headers)    
        httpResponse = urllib.request.urlopen(httpRequest)
    
        responseBody = httpResponse.read() # read() returns the body in BYTES.
        
        return responseBody

    @staticmethod
    def POST(url, jsonData = None, headers = {}):

        encodedJsonData = HTTP.__convertDataForMethod(jsonData, "post")

        # We can only convert the json data into bytes if we actually have some data.
        if encodedJsonData is not None:
            bytes = encodedJsonData.encode("utf-8") # data needs to be in bytes when being sent.
        else:
            bytes = None

        httpRequest = urllib.request.Request(url, bytes, headers)
        
        httpResponse = urllib.request.urlopen(httpRequest)
        responseBody = httpResponse.read()

        return responseBody

    @staticmethod
    def __convertDataForMethod(jsonData, method):

        # Ensure we haven't been passed nothing.
        if jsonData is None:
            return None

        # Convert appropriately.
        if method.lower() == "post":
            return json.dumps(jsonData)
        elif method.lower() == "get":
            if jsonData:
                jsonData = urllib.parse.urlencode(jsonData)
                return jsonData
        else:
            return None

# Simple class which provides some useful methods for working with the file system.
class FileSystem:
    @staticmethod
    def absolutePath(filePath):
        return os.path.abspath(filePath)

    # Does nothing if it already exists.
    @staticmethod
    def createDirectory(directoryPath):
        destinationDirectory = FileSystem.absolutePath(directoryPath)
        os.makedirs(destinationDirectory, exist_ok=True)

    # Throws an error if the file already exists.
    @staticmethod
    def createFile(inDirectory, filename):
        FileSystem.createDirectory(inDirectory)
        filepath = os.path.join(inDirectory, filename)
        open(filepath, "x").close()

    # Takes a path to a file and copies that file to the newLocation 
    @staticmethod
    def copyFile(filePath, newLocation):
        shutil.copy(filePath, newLocation)

    # Takes an array of a file paths and a new path and copies
    # those files to the new path.
    
    # Maintains one layer of depth. So the file will be in the deepest
    # folder that it was in. For example, if the file is /users/user/folder/file.fi
    # and we are copying it to /shared/ then its new location will be:
    # /shared/folder/file.fi
    @staticmethod
    def copyFiles(fileList, newLocation):
        
        for filePath in fileList:
            absolutePath = os.path.abspath(filePath)

            directory = os.path.dirname(absolutePath)
            folderName = os.path.basename(directory)

            destinationDirectory = os.path.join(newLocation, folderName)

            FileSystem.createDirectory(destinationDirectory)
            FileSystem.copyFile(filePath, destinationDirectory)


    # Starting at 'root', searches recursively for all files ending
    # with the string 'filetype'
    @staticmethod
    def findFiles(filetype, root):
        # Remove the dot if it was included
        if filetype[0] == ".":
            filetype = filetype[1:len(filetype)]
        
        found = [];
        
        for root, dirs, files in os.walk(root):
            for filename in files:
                if re.match(".*\." + filetype + "$", filename):
                    found.append(os.path.join(root, filename))
                
        return found

    # Starting at 'root', searches recursively for any files that have a
    # filetype that is in the array 'filetypes'.
    @staticmethod
    def findAnyFiles(filetypes, root):
        found = []

        for filetype in filetypes:
            foundFiles = FileSystem.findFiles(filetype, root)
            for foundFile in foundFiles:
                found.append(foundFile)

        return found

    @staticmethod
    def readFileIntoString(filePath):
        string = ""

        with open(filePath, "r") as file:
            string = file.read()

        return string

    # OVERWRITES the file.
    @staticmethod 
    def writeStringIntoFile(filepath, string):

        directory, filename = os.path.split(filepath)
        FileSystem.createDirectory(directory) # does nothing if it already exits

        f = open(filepath, mode="wt", encoding="utf-8")
        f.write(string)
        f.close()

    @staticmethod
    def writeBytesIntoFile(filepath, bytesToWrite):
        directory, filename = os.path.split(filepath)
        FileSystem.createDirectory(directory) # does nothing if it already exits

        f = open(filepath, mode="wb")
        f.write(bytesToWrite)
        f.close()

    @staticmethod
    def writeDictIntoFile(filepath, dictToWrite, separator):
        f = open(filepath, mode="wt")

        for key, value in dictToWrite.items():
            line = "{}{}{}\n".format(key, separator, value)
            f.write(line)

        f.close()

    # Opens a file and reads it into an array where each element in the 
    # array is a line.
    @staticmethod
    def readFileIntoLinesArray(filePath):
        linesArray = []

        with open(filePath, "r") as file:
            fileText = file.read()
            linesArray = fileText.splitlines()

        return linesArray

if __name__ == "__main__":

    def __parseArgs():
        # Command Line Arguments
        argParser = argparse.ArgumentParser()

        # Can either "build" a devlog or "init" a new devlog
        argParser.add_argument("command", choices=["build", "init"])

        argParser.add_argument("-l", "--location", required=False, default=".",
            help="init: the location to create the new devlog. build: the location of an already existing devlog you wish to build")

        argParser.add_argument(
            "-i", 
            "--incremental", 
            help="only build the entries that have been updated since the last build",
            action="store_true",
            required=False)
        
        argParser.add_argument(
            "-x", 
            "--examples", 
            required=False,
            action="store_true",
            help="whether or not to include example entries in the new directory when performing an 'init'")

        args = argParser.parse_args()

        return args
    
    # Testing
    def printArgs(args):
        # Command
        print(args.command)
        # Build
        print(args.location)
        print(args.incremental) # bool
        # Init
        print(args.location)
        print(args.examples) # bool
    
    args = __parseArgs()
    printArgs(args)
    devlog = Devlog()

    if args.command == "build":
        devlog.build(args.location, args.incremental)
    elif args.command == "init":
        devlog.initialise(args.location, args.examples)
    else:
        print("Error: Unknown Command.")
