# -*- coding: utf-8 -*-
import os
import datetime
import dxTmp
import usdCommonSetup

import sys
sys.path.append('/backstage/libs/python_lib')

TractorRoot = '/backstage/apps/Tractor/applications/linux/Tractor-2.3'
sys.path.append( '%s/lib/python2.7/site-packages' % TractorRoot )
import tractor.api.author as author
TRACTOR_IP = '10.0.0.25'
# TRACTOR_IP = '10.0.0.73'

import json

from pymongo import MongoClient
import dxConfig
import requests
import parse_quicktime

client = MongoClient(dxConfig.getConf("DB_IP"))

excludeNameList = ['daeseok.chae', 'rmantd', 'wonchul.kang']
# showList = ["asd", "asd01", "asd02", "asd03", "mrm", "mya"]
showList = ['srh']

API_KEY = "c70181f2b648fdc2102714e8b5cb344d"

def setOutDir(exportFile, outputDir, datatype):
    basename = os.path.splitext(os.path.basename(exportFile))[0]
    return os.path.join(outputDir, datatype, basename)

def getCheckInList(projectName = "ssr"):
    project = {}
    project['api_key'] = API_KEY
    project['category'] = 'Active'
    project['name'] = projectName
    infos = requests.get("http://%s/dexter/search/project.php" % (dxConfig.getConf('TACTIC_IP')),
                         params=project).json()

    # pprint.pprint(infos)
    try:
        showCode = infos[0]['code']
    except:
        return {}

    snapshot = {}
    snapshot['api_key'] = API_KEY
    snapshot['project_code'] = showCode
    # snapshot['shot_code'] = 'ZMA_2670'
    snapshot['process'] = 'animation'
    snapshot['context'] = 'animation/animation'
    # snapshot['status'] = 'OK'
    snapshot['start_date'] = datetime.date.today() - datetime.timedelta(days = 1)
    snapshot['end_date'] = datetime.date.today() - datetime.timedelta(days = 1)

    infos = requests.get("http://%s/dexter/search/snapshot_file.php" % (dxConfig.getConf('TACTIC_IP')),
                         params=snapshot).json()

    checkInDict = {}
    print "total checkin count :", len(infos)
    for i in infos:
        path = i['path']  # Mov Location
        shot = i['task_name']
        name = i['login']
        time = i['timestamp']

        # pprint.pprint(i)
        if checkInDict.has_key(shot):
            # if time > checkInDict[shot]["time"]:
            if not time > checkInDict[shot]['time']:
                print time, ">", checkInDict[shot]['time'], "skip"
                continue
        print path
        if os.path.splitext(path)[-1] == ".mov":
            try:
                m = parse_quicktime.Mov(path)
                m.parse()
            except:
               print "parse fail : %s" % shot
               continue
            if not m.userMetaData.has_key("mayaFilePath"):
                continue

            path = m.userMetaData['mayaFilePath']

            checkInDict[shot] = {"name": name,
                                 "shot": shot,
                                 "path": path,
                                 "time": time}
        # print "User :", name, "\tshot :", shot, "\tfile :", path, "\ttime :", time

    print "filtering shot count :", len(checkInDict.keys())
    print "check-in shot List :", checkInDict.keys()
    print

    return checkInDict


def getAutoCacheList(project = "ssr"):
    pipeDB = client.PIPE_PUB
    workDB = client.WORK

    yesterday = datetime.date.today() - datetime.timedelta(days = 1)
    today = datetime.date.today() + datetime.timedelta(days = 0)
    # print dir(yesterday)
    # 1. get save ani scene file today
    shotDict = {}

    query = {"action":"save",
             "task":"ani",
             "$and":[]}
    query["$and"].append({"time":{"$gte":yesterday.isoformat()}})
    query["$and"].append({"time":{"$lte":today.isoformat()}})

    for item in workDB[project].find(query, sort=[("time", -1)]):
        if not shotDict.has_key(item["name"]) and os.path.exists(item["filepath"]) and not item['user'] in excludeNameList:
            shotDict[item["name"]] = (item["filepath"], item['user'])
    # cursor.distinct("name")

    pipeQuery = {"task":"ani",
                 "$and":[],
                 "enabled":True}
    pipeQuery["$and"].append({"time":{"$gte":yesterday.isoformat()}})
    pipeQuery["$and"].append({"time":{"$lte":today.isoformat()}})

    for shotName in pipeDB[project].find(pipeQuery).distinct("shot"):
        try:
            if shotDict.has_key(shotName):
                pipeQuery["shot"] = shotName
                print pipeQuery, shotName, shotDict[shotName]
                filePath = pipeDB[project].find_one(pipeQuery)['files']['maya_dev_file'][0]
                shotDict[shotName][0] = filePath
        except:
            continue
            # shotDict.pop(shotName)

    pipeQuery["action"] = "export"

    for shotName in workDB[project].find(pipeQuery).distinct("shot"):
        try:
            if shotDict.has_key(shotName):
                shotDict.pop(shotName)
                # pipeQuery["shot"] = shotName
                # print pipeQuery, shotName, shotDict[shotName]
                # filePath = pipeDB[project].find_one(pipeQuery)['files']['maya_dev_file'][0]
                # shotDict[shotName][0] = filePath
        except Exception as e:
            print e.message
            continue
            # shotDict.pop(shotName)

    return shotDict

def excludeShotList(project = "ssr"):
    workDB = client.WORK
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    today = datetime.date.today() + datetime.timedelta(days=0)

    pipeQuery = {"task": "ani",
                 "$and": [],
                 "enabled": True}
    pipeQuery["$and"].append({"time": {"$gte": yesterday.isoformat()}})
    pipeQuery["$and"].append({"time": {"$lte": today.isoformat()}})
    pipeQuery["action"] = "export"

    shotDict = []
    print "already export shot list"
    for shotName in workDB[project].find(pipeQuery).distinct("shot"):
        print shotName
        try:
            if not shotName in shotDict:
                shotDict.append(shotName)
            # if not shotDict.has_key(shotName):
            #     shotDict[shotName] = []
            # for exportData in workDB[project].find(pipeQuery):
            #     scenePath = exportData['filepath']
            #     if not scenePath in shotDict[shotName]:
            #         shotDict[shotName].append(scenePath)
        except Exception as e:
            print e.message
            continue
            # shotDict.pop(shotName)

    return shotDict

NAME = 0
ACTION = 1
VISIBLE = 2

def getVersion(outputDir, category, nodeInfo):
    if category == "ani" or category == "zenn" or category == "sim":
        nsLayer, nodeName = nodeInfo[NAME].split(":")
        nsLayerPath = os.path.join(outputDir, category, nsLayer)
        if not os.path.exists(nsLayerPath):
            return "v001"
        source = list()
        for i in os.listdir(nsLayerPath):
            if os.path.isdir(os.path.join(nsLayerPath, i)):
                if i[0] == 'v':
                    source.append(i)
        source.sort()
        if source:
            return 'v%03d' % (int(source[-1][1:]) + 1)
        else:
            return 'v001'
    else:
        pubPath = os.path.join(outputDir, category)

        if not os.path.exists(pubPath):
            return "v001"
        source = list()
        for i in os.listdir(pubPath):
            if os.path.isdir(os.path.join(pubPath, i)):
                if i[0] == 'v':
                    source.append(i)
        source.sort()
        if source:
            return 'v%03d' % (int(source[-1][1:]) + 1)
        else:
            return 'v001'

for expShow in showList:
    autoCacheList = getCheckInList(expShow)
    excludeShot = excludeShotList(expShow)

    for shotName in autoCacheList.keys():
        if not shotName in excludeShot:
            continue

        autoCacheList.pop(shotName)
        print "exclude shot :", shotName

    for key in autoCacheList.keys():
        orgSceneFile = autoCacheList[key]["path"]
        userName = autoCacheList[key]["name"]

        # make tmp file
        tmpClass = dxTmp.dxTmp(orgSceneFile)
        tmpClass.setBackupDirName("CacheOut_Submitter")
        tmpClass.username = userName
        tmpClass.calcTmpFile()
        try:
            sceneFilePath = tmpClass.save()
        except:
            continue
        # sceneFilePath = str(tmpClass)

        splitPath = sceneFilePath.split('/')
        showIndex = splitPath.index("show")
        if showIndex == -1:
            break

        show = splitPath[showIndex + 1]
        shot = splitPath[showIndex + 4]

        showDir = usdCommonSetup.GetShowDir(show)
        outDir = '{SHOWDIR}/shot/{SEQ}/{SHOT}'.format(SHOWDIR=showDir, SEQ=shot.split('_')[0], SHOT=shot)

        jsonFile = orgSceneFile.replace(".mb", ".json")
        if not os.path.exists(jsonFile) or not os.path.isfile(jsonFile):
            continue

        f = open(jsonFile, "r")
        sceneGraph = json.load(f)

        if not sceneGraph.has_key("mayaVersion"):
            mayaVer = "2017"
        else:
            mayaVer = sceneGraph['mayaVersion']

        cmd = ["/backstage/bin/DCC", 'rez-env']
        cmd += sceneGraph['rezResolve'].split(' ')
        cmd += ['--', "mayapy", '/backstage/apps/Maya/toolkits/dxsUsd/BatchScene.py']
        cmd += ["--srcfile", sceneFilePath] # export when scenefile.
        cmd += ["--outdir", outDir] # export data location
        cmd += ["--user", userName]
        cmd += ['--host', 'tractor']

        print "#Cmd :"
        print " ".join(cmd)

        # calc data and
        jsonFile = orgSceneFile.replace(".mb", ".json")
        if not os.path.exists(jsonFile) or not os.path.isfile(jsonFile):
            continue

        basename = os.path.splitext(os.path.basename(orgSceneFile))[0]
        envkey = ''
        serviceKey = 'USER||Cache'
        job = author.Job()
        job.title = '(USD Animation Cache Out) %s' % str(basename)
        job.comment = '# output dir : %s' % str(outDir)
        job.metadata = 'source file : %s' % str(orgSceneFile)
        job.envkey = [envkey]
        job.service = serviceKey
        job.maxactive = 1
        job.tier = 'cache'
        job.projects = ['export']
        job.tags = ['GPU']

        JobTask = author.Task(title='Job')
        JobTask.serialsubtasks = 1
        job.addChild(JobTask)

        exportJob = author.Task(title='tractor spool')
        exportJob.serialsubtasks = 0

        with open(jsonFile, "r") as f:
            sceneGraph = json.load(f)
            if len(sceneGraph['camera']) >= 1:
                camJob = author.Task(title='camera export')
                for node in sceneGraph['camera']:
                    if node[1] == 0 or not node[2]: # action : none or visibility off
                        continue
                    camSubTask = author.Task(title='camera %s export' % str(node[0]))
                    version = getVersion(outDir, "cam", node)
                    newCmd = cmd + ["--camera", "%s=%s" % (version, node[0])]
                    camSubTask.addCommand(author.Command(argv = newCmd, service = serviceKey))
                    camJob.addChild(camSubTask)
                exportJob.addChild(camJob)

            if len(sceneGraph["layout"]) >= 1:
                setJob = author.Task(title='layout export')
                for node in sceneGraph['layout']:
                    if not node[2]:  # visibility off
                        continue
                    setSubTask = author.Task(title='layout %s export' % str(node[0]))
                    version = getVersion(outDir, "set", node)
                    newCmd = cmd + ["--layout", "%s=%s" % (version, node[0])]
                    setSubTask.addCommand(author.Command(argv=newCmd, service=serviceKey))
                    setJob.addChild(setSubTask)
                exportJob.addChild(setJob)

            if len(sceneGraph["geoCache"]) >= 1:
                meshJob = author.Task(title='mesh export')
                for node in sceneGraph['geoCache']:
                    try:
                        if node[1] == 0 or not node[2]:  # action : none or visibility off
                            continue
                        meshSubTask = author.Task(title='mesh %s export' % str(node[0]))
                        version = getVersion(outDir, "ani", node)
                        newCmd = cmd + ["--mesh", "%s=%s" % (version, node[0]), "--zenn", "--rigUpdate"]
                        meshSubTask.addCommand(author.Command(argv=newCmd, service=serviceKey))
                        meshJob.addChild(meshSubTask)
                    except:
                        print "version Parse Fail"
                        continue
                exportJob.addChild(meshJob)

            if len(sceneGraph["components"]) >= 1:
                meshJob = author.Task(title='mesh export')
                for node in sceneGraph['components']:
                    try:
                        if node[1] == 0 or not node[2]:  # action : none or visibility off
                            continue
                        meshSubTask = author.Task(title='mesh %s export' % str(node[0]))
                        version = getVersion(outDir, "ani", node)
                        newCmd = cmd + ["--mesh", "%s=%s" % (version, node[0]), "--zenn", "--rigUpdate"]
                        meshSubTask.addCommand(author.Command(argv=newCmd, service=serviceKey))
                        meshJob.addChild(meshSubTask)
                    except:
                        print "version Parse Fail"
                        continue
                exportJob.addChild(meshJob)
            #
            # if sceneGraph.has_key('sim') and len(sceneGraph["sim"]) >= 1:
            #     simJob = author.Task(title='sim export')
            #     for node in sceneGraph['sim']:
            #         try:
            #             if node[1] == 0 or not node[2]:  # action : none or visibility off
            #                 continue
            #             simSubTask = author.Task(title='sim %s export' % str(node[0]))
            #             version = getVersion(outDir, "sim", node)
            #             newCmd = cmd + ["--sim", "%s=%s" % (version, node[0]), "--zenn"]
            #             simSubTask.addCommand(author.Command(argv=newCmd, service=serviceKey))
            #             simJob.addChild(simSubTask)
            #         except:
            #             print "version Parse Fail"
            #             continue
            #     exportJob.addChild(simJob)

        # exportJob.addCommand(
        #     author.Command(argv=opts, envkey=job.envkey, tags=['py']))
        JobTask.addChild(exportJob)

        job.priority = 100
        author.setEngineClientParam(hostname=TRACTOR_IP, port=80,
                                    user=userName, debug=True)
        job.spool()
        author.closeEngineClient()

