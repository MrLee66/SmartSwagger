# coding=utf-8
import argparse
import copy
import time
import requests
import json
import os
import sys


# DTO Generator
def __generateModel(interfaceModel, filepath, matchedList):
    # read exclude DTO
    includeModels = json.loads(open('config.json').read())['IncludesModels']

    excludeModels = json.loads(open('config.json').read())['ExcludeModels']

    # exclude models by config
    for excludeModel in excludeModels:
        if excludeModel in interfaceModel['title']:
            return

    isRelated = [False]

    # judge if model is needed
    for matchStr in matchedList:
        if matchStr in interfaceModel['title']:
            isRelated[0] = True
            break

    # include extra need to be generated DTOs
    if interfaceModel['title'] not in includeModels and not isRelated[0]:
        return

    dTOTemplate = open('DTOTemplate.tpl', 'r')
    dTOTemplateContent = dTOTemplate.read()

    propertyTemplate = open('PropertyTemplate.tpl', 'r')
    propertyTemplateContent = propertyTemplate.read()
    requiredList = []
    if 'required' in interfaceModel:
        requiredList = interfaceModel['required']
    modelProperties = dict()
    if 'properties' in interfaceModel:
        modelProperties = interfaceModel['properties']

    propertyMemberList = []

    for propertyKey in modelProperties:
        propertyTemplateStr = copy.deepcopy(propertyTemplateContent)
        propertyBody = modelProperties[propertyKey]
        if 'type' in propertyBody:
            if propertyKey in requiredList:
                propertyStr = propertyKey + ':' + propertyBody['type']
                propertyTemplateStr = propertyTemplateStr.replace('${PropertyDescription}', propertyBody['description'])
                propertyTemplateStr = propertyTemplateStr.replace('${PropertyDefine}', propertyStr)
            else:
                propertyStr = propertyKey + '?:' + propertyBody['type']
                propertyTemplateStr = propertyTemplateStr.replace('${PropertyDescription}',
                                                                  str(propertyBody.get('description')))
                propertyTemplateStr = propertyTemplateStr.replace('${PropertyDefine}', propertyStr)
        else:
            if propertyKey in requiredList:
                propertyStr = propertyKey + ':' + propertyBody['originalRef']
                propertyTemplateStr = propertyTemplateStr.replace('${PropertyDescription}', propertyBody['description'])
                propertyTemplateStr = propertyTemplateStr.replace('${PropertyDefine}', propertyStr)
            else:
                propertyStr = propertyKey + '?:' + propertyBody['originalRef']
                propertyTemplateStr = propertyTemplateStr.replace('${PropertyDescription}',
                                                                  str(propertyBody.get('description')))
                propertyTemplateStr = propertyTemplateStr.replace('${PropertyDefine}', propertyStr)
        propertyMemberList.append(propertyTemplateStr)
    # combine properties
    dTOTemplateContent = dTOTemplateContent.replace('${PropertiesArea}', '\n'.join(propertyMemberList))
    dTOTemplateContent = dTOTemplateContent.replace('${Describe}', str(interfaceModel.get('description')))
    dTOTemplateContent = dTOTemplateContent.replace('${DTOName}', interfaceModel['title'])

    # global replace rules
    f = open('config.json', 'r')
    rules = json.loads(f.read()).get('ReplaceRules')
    for toReplace in rules:
        dTOTemplateContent = dTOTemplateContent.replace(toReplace, rules[toReplace])
    # print to file
    f = open(os.path.join(filepath, interfaceModel['title']) + '.ts', 'w', encoding='UTF-8')
    f.write(dTOTemplateContent)


def __getConstructInfos(aPIKey):
    apiInterface = aPIs[aPIKey]

    constructInfo = dict()

    constructInfo['Url'] = aPIKey
    methodBody = {}
    for methodKey in apiInterface:
        constructInfo['MethodType'] = methodKey
        methodBody = apiInterface[methodKey]
    constructInfo['MethodName'] = methodBody['operationId']
    constructInfo['MethodDescribe'] = methodBody['summary']
    constructInfo['QueryParams'] = []
    constructInfo['PathParams'] = []
    constructInfo['BodyParams'] = []
    response = methodBody.get('responses').get('200')
    if 'responseSchema' in response:
        constructInfo['ReturnContent'] = str(response.get('responseSchema').get('originalRef')).replace('«',
                                                                                                        "<<").replace(
            "»", ">>")
    else:
        constructInfo['ReturnContent'] = 'any'
    constructInfo['Tag'] = methodBody['tags'][0]
    for param in methodBody['parameters']:
        if param['in'] != 'header':
            if param['in'] == 'query':
                constructInfo['QueryParams'].append(param)
            elif param['in'] == 'path':
                constructInfo['PathParams'].append(param)
            else:
                constructInfo['BodyParams'].append(param)
    constructInfos.append(constructInfo)


# API Group Divider
def __divideGroups():
    for aPIKey in aPIMaps:
        for constructInfo in constructInfos:
            if aPIKey == constructInfo['Tag']:
                aPIMaps[aPIKey].append(constructInfo)


# Method Child Method Generator
def __generateChildUrl():
    for aPIKey in aPIMaps:
        aPIInterface = aPIMaps[aPIKey]
        urlList = []
        for methodBody in aPIInterface:
            if 'Url' in methodBody:
                urlList.append(methodBody['Url'])
        mainUrl = min(urlList, key=len)
        baseUrl = dict()
        baseUrl['BaseUrl'] = mainUrl

        for methodBody in aPIInterface:
            if 'Url' in methodBody:
                if methodBody['Url'] != mainUrl:
                    methodBody['Url'] = methodBody['Url'].replace(mainUrl, '')
                elif methodBody['Url'] == mainUrl:
                    methodBody['Url'] = ''
        aPIInterface.append(baseUrl)


# API Service Generator
def __generateService(aPIInterfaceMaps, filepath):
    print('\033[1;34m*********Begin To Process Services .).)*********\033[0m')
    serviceTemplate = open('ServiceTemplate.tpl')
    serviceTemplateContent = serviceTemplate.read()

    methodTemplate = open('MethodTemplate.tpl')
    methodTemplateContent = methodTemplate.read()

    for aPIInterFaceKey in aPIInterfaceMaps:
        aPIInterfaceServiceTemplate = copy.deepcopy(serviceTemplateContent)
        methodList = aPIInterfaceMaps[aPIInterFaceKey]
        baseUrl = []
        aPIInfo = []
        for member in methodList:
            if 'BaseUrl' in member:
                baseUrl.append(member.get('BaseUrl'))
            if 'Name' in member:
                aPIInfo.append(member)
        # init API Service info
        aPIInterfaceServiceTemplate = aPIInterfaceServiceTemplate.replace('${Describe}', aPIInterFaceKey)

        aPIInterfaceServiceTemplate = aPIInterfaceServiceTemplate.replace('${SerViceName}', aPIInfo[0].get('Name'))

        aPIInterfaceServiceTemplate = aPIInterfaceServiceTemplate.replace('${BaseUrl}', baseUrl[0])
        # Combined Methods
        combinedMethodsList = []
        # Begin to combine
        for aPIMethod in methodList:
            # remove others object,leave method only
            if 'BaseUrl' in aPIMethod:
                continue
            if 'Name' in aPIMethod:
                continue
            # init method info

            aPIInterFaceMethodTemplate = copy.deepcopy(methodTemplateContent)
            aPIInterFaceMethodTemplate = aPIInterFaceMethodTemplate.replace('${MethodDescribe}',
                                                                            ' Method Description ' + aPIMethod.get(
                                                                                'MethodDescribe'))
            aPIInterFaceMethodTemplate = aPIInterFaceMethodTemplate.replace('${MethodName}',
                                                                            aPIMethod.get('MethodName'))
            aPIInterFaceMethodTemplate = aPIInterFaceMethodTemplate.replace('${MethodType}',
                                                                            aPIMethod.get('MethodType'))
            aPIInterFaceMethodTemplate = aPIInterFaceMethodTemplate.replace('${ReturnContent}',
                                                                            aPIMethod.get('ReturnContent'))

            # method constructor&param description&param constructor
            paramDescriptionList = []
            paramMemberList = []
            paramConstructorList = []

            for pathParam in aPIMethod.get('PathParams'):
                # param description
                pathParamDes = ' @param ' + pathParam.get('name') + ' ' + pathParam.get('description')
                paramDescriptionList.append(pathParamDes)

                # param list info
                if pathParam.get('required'):
                    queryParamMember = pathParam.get('name') + ':' + pathParam.get('type')
                else:
                    queryParamMember = pathParam.get('name') + '?:' + pathParam.get('type')
                paramMemberList.append(queryParamMember)

            for queryParam in aPIMethod.get('QueryParams'):
                # param description
                queryParamDes = ' @param ' + queryParam.get('name') + ' ' + queryParam.get('description')
                paramDescriptionList.append(queryParamDes)

                # param list info
                if queryParam.get('required'):
                    queryParamMember = queryParam.get('name') + ':' + queryParam.get('type')
                else:
                    queryParamMember = queryParam.get('name') + '?:' + queryParam.get('type')
                paramMemberList.append(queryParamMember)

                # param construct
                queryParamConstructor = 'Object.assign(params,' + queryParam.get('name') + '?{' + queryParam.get(
                    'name') + '}:{ })'
                paramConstructorList.append(queryParamConstructor)
            for bodyParam in aPIMethod.get('BodyParams'):
                # param description
                bodyParamDes = '@param ' + bodyParam.get('name') + ' ' + str(bodyParam.get('description'))
                paramDescriptionList.append(bodyParamDes)

                #  method param list
                if bodyParam.get('required'):
                    if 'schema' in bodyParam:
                        bodyParamMember = bodyParam.get('name') + ':' + str(bodyParam.get('schema').get('originalRef'))
                    else:
                        bodyParamMember = bodyParam.get('name') + ': any'

                else:
                    if 'schema' in bodyParam:
                        bodyParamMember = bodyParam.get('name') + ':' + str(bodyParam.get('schema').get('originalRef'))
                    else:
                        bodyParamMember = bodyParam.get('name') + '?: any'
                paramMemberList.append(bodyParamMember)

            # combine method info

            paramDescriptionStr = '\n * '.join(paramDescriptionList)

            paramMemberStr = ',\n           '.join(paramMemberList)

            paramConstructorStr = ',\n   '.join(paramConstructorList)

            aPIInterFaceMethodTemplate = aPIInterFaceMethodTemplate.replace('${ParamsDescribe}', paramDescriptionStr)

            aPIInterFaceMethodTemplate = aPIInterFaceMethodTemplate.replace('${MethodParams}', paramMemberStr)

            aPIInterFaceMethodTemplate = aPIInterFaceMethodTemplate.replace('${ParamsArea}', paramConstructorStr)

            # combineUrl by situation of params

            # if exist path param
            combineUrl = '`${' + aPIInfo[0].get('Name') + '.URL}`' + aPIMethod.get('Url')
            if len(aPIMethod.get('PathParams')) > 0:
                pathParamUrlConstructorList = []
                for pathParam in aPIMethod.get('PathParams'):
                    pathParamConstructor = '${' + pathParam.get('name') + '}'
                    pathParamUrlConstructorList.append(pathParamConstructor)
                combineUrl = '`${' + aPIInfo[0].get('Name') + '.URL}' + '/' + '/'.join(
                    pathParamUrlConstructorList) + '`'

            # if exist body param
            elif len(aPIMethod.get('BodyParams')) > 0:
                combineUrl = combineUrl + ',' + aPIMethod.get('BodyParams')[0].get('name')

            else:
                combineUrl = combineUrl + ",params"

            aPIInterFaceMethodTemplate = aPIInterFaceMethodTemplate.replace('${CombineUrl}', combineUrl)

            # if there is no query param,remove [const param = {}]
            if len(aPIMethod.get('QueryParams')) == 0:
                aPIInterFaceMethodTemplate = aPIInterFaceMethodTemplate.replace('${ConstParam}', '')
            else:
                aPIInterFaceMethodTemplate = aPIInterFaceMethodTemplate.replace('${ConstParam}', 'const params = { };')

            combinedMethodsList.append(aPIInterFaceMethodTemplate)
        # replace methods
        aPIInterfaceServiceTemplate = aPIInterfaceServiceTemplate.replace('${MethodsArea}',

                                                                          '\n'.join(combinedMethodsList))
        aPIInterfaceServiceTemplate = aPIInterfaceServiceTemplate.replace('${GeneratedTime}',
                                                                          time.strftime("%Y-%m-%d",
                                                                                        time.localtime()))
        # global replace rules
        f = open('config.json', 'r')
        rules = json.loads(f.read()).get('ReplaceRules')
        for toReplace in rules:
            aPIInterfaceServiceTemplate = aPIInterfaceServiceTemplate.replace(toReplace, rules[toReplace])
        # print to file
        f = open(os.path.join(filepath, aPIInfo[0].get('Name')) + '.ts', 'w', encoding='UTF-8')
        f.write(aPIInterfaceServiceTemplate)
    print('\033[1;32mGenerate Services Successfully! (^_^)\033[0m')


# cmd process
content = dict()

savepath = ''

parser = argparse.ArgumentParser(description='The API Tool To Help You Generate Files Easily!')

parser.add_argument('-url', help='The Swagger Address')

parser.add_argument('-group', help='The API Group Name')

parser.add_argument('-address', help='The Total Interface Address')

parser.add_argument('-savepath', help='The Path To Save Generated Files')

parser.add_argument('-noservice', help='Whether to generate services', action='store_true')

# parse cmd params
args = parser.parse_args()

if args.url and args.group and args.savepath:
    groupSplitList = str(args.group).split(' ')
    swagger_address = args.url + '/api-docs?group=' + '%20'.join(groupSplitList)
    if not os.path.isdir(args.savepath):
        print('\033[1;31mPlease Choose a Directory Not\033[0m', end='')
        print('\033[1;33m' + + args.savepath + '\033[0m')
        sys.exit(0)
    response = requests.get(swagger_address)
    if response.status_code != 200:
        print('\033[1;31mPlease Check The Url: status code=>  \033[0m', end='')
        print('\033[1;33m' + str(response.status_code) + '\033[0m')
        sys.exit(0)
    content = json.loads(str(requests.get(swagger_address).content, 'UTF-8'))
    savepath = args.savepath

elif args.address and args.savepath:
    response = requests.get(args.address)
    if response.status_code != 200:
        print('\033[1;31mPlease Check The Url: status code=>  \033[0m', end='')
        print('\033[1;33m' + str(response.status_code) + '\033[0m')
        sys.exit(0)
    content = json.loads(str(requests.get(args.address).content, 'UTF-8'))
    savepath = args.savepath
else:
    print('\033[1;31mPlease Check Your Params! We Need [url]&[group]&[savepath]\033[0m')
    sys.exit(0)
# begin to process
tags = []
aPIMaps = dict()
totalAPIDes = dict()
for tag in content['tags']:
    tags.append(tag['name'])
    aPIDesStr = tag['description']
    aPIDes = dict()
    aPIDes['Describe'] = aPIDesStr
    aPIDesStrSplit = str(aPIDesStr).split(' ')
    aPIDesStrSplit.pop()
    aPIDes['Name'] = ''.join(aPIDesStrSplit) + 'Service'
    totalAPIDes[tag['name']] = aPIDes

for tag in tags:
    aPIMaps[tag] = []
    aPIMaps[tag].append(totalAPIDes.get(tag))
aPIs = content['paths']

constructInfos = []

for key in aPIs:
    __getConstructInfos(key)
__divideGroups()
__generateChildUrl()

matchList = []

for key in aPIMaps:
    for member in aPIMaps[key]:
        if 'BaseUrl' in member:
            pathSplitList = str(member['BaseUrl']).split('/')
            matchList.append(str(pathSplitList[len(pathSplitList) - 1]))
            break

# models process

interfaceModels = content['definitions']
# remind info
print('\033[1;35mAuto Find Key Words:\033[0m', end='')
print('\033[1;33m' + str(matchList) + '\033[0m')

print('\033[1;34m*********Begin To Process Models .).)*********\033[0m')

matchList = list(map(lambda x: x[:-3].capitalize(), matchList))

for interfaceModelKey in interfaceModels:
    model = interfaceModels[interfaceModelKey]
    __generateModel(model, savepath, matchList)
print('\033[1;32mGenerate Models Successfully! (^_^)\033[0m')
# services process,judge by param to decide whether to generate service

if not args.noservice:
    __generateService(aPIMaps, savepath)
