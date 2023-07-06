
import os.path

if (__name__ == "__main__"):
    from lxml import etree
else:

    # from SCons.Script import DefaultEnvironment
    from SCons.Script import ARGUMENTS

    # try:
    # Import("env") #, "projenv")
    env = DefaultEnvironment()

    try:
        from lxml import etree
    except ImportError:
        env.Execute("$PYTHONEXE -m pip install lxml")
        from lxml import etree

build = {
    'name': '',
    'device': '',
    'defines': [],
    'includes': ['.'],
    'sources': [],
    'cflags': [],
    'ldflags': [],
}

def debug_print():
    for key in build:
        print(key, build[key])

def clean_xml_namespaces(root):
    for element in root.getiterator():
        if isinstance(element, etree._Comment):
            continue
        element.tag = etree.QName(element).localname
    etree.cleanup_namespaces(root)

def parseChildren(element, parsers):
    for key, value in parsers.items():
        matching: list = element.findall(key)
        for e in matching:
            value(e)

def listValues(element):
    list_values = element.find("ListValues")
    values = list_values.findall("Value")
    return [element.text for element in values]

class Properties:
    def avrdevice(element):
        build['defines'].append("__" + element.text + "__")
        build['device'] = element.text

    def name(element):
        build['name'] = element.text

    propertyParsers = {
        "avrdevice": avrdevice,
        "Name": name
    }

    def __init__(self, group):
        parseChildren(group, self.propertyParsers)

class Configuration:

    def DefSymbols(element):
        defines = listValues(element)
        build['defines'].extend(defines)

    @staticmethod
    def fixInclude(path):
        # replace backslash with forwardslash and remove '../' at beginning
        if path.startswith("../"):
            path = path[3:]
        path = path.replace("\\", "/")
        return path.replace("%24(PackRepoDir)", "/Users/mransom/Documents/Atmel Studio/packs")

    def IncludePaths(element):
        includes = listValues(element)
        includes = map(Configuration.fixInclude, includes)
        build['includes'].extend(includes)

    def PrepareFunctionsForGarbageCollection(element):
        if element.text == "True":
            build['cflags'].append("-ffunction-sections")
            build['cflags'].append("-fdata-sections")
        # "-fdata-sections",

    def AllWarnings(element):
        if element.text == "True":
            build['cflags'].append("-Wall")

    def OptimizationLevel(element):
        if element.text == "Optimize (-O1)":
            build['cflags'].append("-O1")

    def LinkerFlags(element):
        flags = element.text
        build['ldflags'].append("\"-T" + sourceDir + flags[4:] + "\"")

    def GarbageCollectUnusedSections(element):
        if element.text == "True":
            build['ldflags'].append("-Wl,--gc-sections")


    armGccParsers = {
        "armgcc.compiler.symbols.DefSymbols": DefSymbols,
        "armgcc.compiler.directories.IncludePaths": IncludePaths,
        "armgcc.compiler.optimization.PrepareFunctionsForGarbageCollection": PrepareFunctionsForGarbageCollection,
        "armgcc.compiler.warnings.AllWarnings": AllWarnings,
        "armgcc.compiler.optimization.level": OptimizationLevel,
        "armgcc.linker.miscellaneous.LinkerFlags": LinkerFlags,
        "armgcc.linker.optimization.GarbageCollectUnusedSections": GarbageCollectUnusedSections,
    }

    def __init__(self, group):

        if config not in group.attrib['Condition']:
            return
        armGcc = group.find("ToolchainSettings").find("ArmGcc")
        parseChildren(armGcc, self.armGccParsers)


class PropertyGroup:
    def __init__(self, group):
        if group.attrib.get('Condition'):
            Configuration(group)
        else:
            Properties(group)

class ItemGroup:

    @staticmethod
    def fixPath(path):

        return path.replace("\\", "/")

    def __init__(self, element):
        items = element.findall("Compile")
        files = [e.attrib['Include'] for e in items]
        sources = [self.fixPath(f) for f in files]
        build['sources'].extend(sources)

class CProj:

    cproj_parsers = {
        "PropertyGroup": PropertyGroup,
        "ItemGroup": ItemGroup
    }

    def __init__(self, root):
        parseChildren(root, self.cproj_parsers)


def parse(filename):

    myparse = etree.XMLParser( )

    tree: etree.ElementTree = etree.parse(filename)

    root: etree.Element = tree.getroot()

    clean_xml_namespaces(root)

    project = CProj(root)

    if int(ARGUMENTS.get("PIOVERBOSE", 0)):
        debug_print()

if (__name__ == "__main__"):
    path = "/Users/mransom/Documents/projects/Transceiver-v4-E-/Transceiver-v4-E-MCU/Transceiver-v4-E-MCU.cproj"
    parse(path)
else:
    path = env.GetProjectOption("custom_cproj")
    config = env.GetProjectOption("custom_cproj_config")

    sourceDir = env.get("PROJECT_SRC_DIR")

    cprojDir = os.path.dirname(path)
    if cprojDir:
        sourceDir = os.path.join(sourceDir, cprojDir, '')

    sourcePathAdjust = os.path.join(os.path.relpath(sourceDir, env.get("PROJECT_SRC_DIR")), '')

    # print("SOURCEDIR: ", sourceDir)

    parse(path)

    def pathToFilter(path):
        return "+<" + sourcePathAdjust + path + ">"

    def includeToBuild(path):
        if not path.startswith('/'):
            return sourceDir + '/' + path
        return path

    def setProjectOption(option, value):
        return env.GetProjectConfig().get("env:" + env["PIOENV"], option, value)

    env.Append(
        CFLAGS = build['cflags'],
        LINKFLAGS = build['ldflags'],
        CPPPATH = list(map(includeToBuild, build['includes'])),
        CPPDEFINES = build['defines'],
        SRC_FILTER = list(map(pathToFilter, build['sources'])),
    )

    print("ATMEL STUDIO PROJECT:", path)
    # print("SOURCES:", env.get("SRC_FILTER"))

    svd_path = "/Users/mransom/Documents/projects/tools/cmsis-svd/data/Atmel/" + build['device'] + '.svd'
    # assert os.path.isfile(svd_path)
    if os.path.isfile(svd_path):
        setProjectOption("debug_svd_path", svd_path)
    else:
        print("Couldn't find SVD for ", build['device'])

    # env.BuildSources(build['sources'])

    # print(env.Dump())
    

    # env.AddPostAction(
    #     "$BUILD_DIR/${PROGNAME}.elf",
    #     env.VerboseAction(" ".join([
    #         "$OBJCOPY", "-O", "ihex", "-R", ".eeprom",
    #         "$BUILD_DIR/${PROGNAME}.elf", "$BUILD_DIR/${PROGNAME}.hex"
    #     ]), "Building $BUILD_DIR/${PROGNAME}.hex")
    # )


