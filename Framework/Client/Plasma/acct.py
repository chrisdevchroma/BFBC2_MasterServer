# -*- coding: utf-8 -*-

from base64 import b64encode, b64decode
from datetime import datetime
from os.path import exists

from ConfigParser import ConfigParser

from Database import Database
from Logger import Log
from Utilities.Packet import Packet

from urllib import quote

db = Database()

logger = Log("PlasmaClient", "\033[33;1m")
logger_err = Log("PlasmaClient", "\033[33;1;41m")


def HandleGetCountryList(self):
    """ User wants to create a new account """

    countryList = GetCountryList(self)

    Packet(countryList).sendPacket(self, "acct", 0x80000000, self.CONNOBJ.plasmaPacketID, logger=logger)
    self.CONNOBJ.plasmaPacketID += 1


def GetCountryList(self):
    countryList = ConfigParser()
    countryList.optionxform = str
    countryList.add_section("PacketData")

    if exists("Data/countryLists/countryList_" + self.CONNOBJ.locale):
        with open("Data/countryLists/countryList_" + self.CONNOBJ.locale) as countryListFile:
            countryListData = countryListFile.readlines()
    else:
        with open("Data/countryLists/default") as countryListFile:
            countryListData = countryListFile.readlines()

    countryList.set("PacketData", "TXN", "GetCountryList")
    countryList.set("PacketData", "countryList.[]", str(len(countryListData)))

    countryId = 0
    for line in countryListData:
        countryList.set("PacketData", "countryList." + str(countryId) + ".ISOCode", line.split("=")[0])
        countryList.set("PacketData", "countryList." + str(countryId) + ".description",
                        line.split("=")[1].replace('"', "").replace("\n", ""))
        countryId += 1

    return countryList


def HandleNuGetTos(self):
    """ Get Terms of Use """

    tos = GetTOS(self)

    Packet(tos).sendPacket(self, "acct", 0x80000000, self.CONNOBJ.plasmaPacketID, logger=logger)
    self.CONNOBJ.plasmaPacketID += 1


def GetTOS(self):
    tos = ConfigParser()
    tos.optionxform = str
    tos.add_section("PacketData")
    tos.set("PacketData", "TXN", "NuGetTos")
    tos.set("PacketData", "version", "20426_17.20426_17")

    if exists("Data/termsOfUse/termsOfUse_" + self.CONNOBJ.locale):
        with open("Data/termsOfUse/termsOfUse_" + self.CONNOBJ.locale) as termsOfUseFile:
            termsOfUse = termsOfUseFile.read()
    else:
        with open("Data/termsOfUse/default") as termsOfUseFile:
            termsOfUse = termsOfUseFile.read()

    termsOfUse = quote(termsOfUse, safe=" ,.'&/()?;®@§[]").replace("%3A", "%3a").replace("%0A",
                                                                                         "%0a") + "%0a%0a%09Battlefield%3a Bad Company 2 Master Server Emulator by B1naryKill3r%0ahttps://github.com/B1naryKill3r/BFBC2_MasterServer"
    tos.set("PacketData", "tos", termsOfUse)
    return tos


def HandleNuAddAccount(self, data):
    """ Final add account request (with data like email, password...) """

    nuid = data.get('PacketData', 'nuid')  # Email
    password = data.get('PacketData', 'password')  # Password

    bd_Day = data.get('PacketData', 'DOBDay')
    bd_Month = data.get('PacketData', 'DOBMonth')
    bd_Year = data.get('PacketData', 'DOBYear')
    birthday = datetime.strptime(bd_Day + " " + bd_Month + " " + bd_Year, "%d %m %Y")
    timeNow = datetime.now()

    country = data.get('PacketData', 'country')

    regResult = ConfigParser()
    regResult.optionxform = str
    regResult.add_section("PacketData")
    regResult.set("PacketData", "TXN", "NuAddAccount")

    if len(nuid) > 32 or len(nuid) < 3:  # Entered user name length is out of bounds
        regResult.set("PacketData", "errorContainer.[]", "1")
        regResult.set("PacketData", "errorCode", "21")
        regResult.set("PacketData", "localizedMessage",
                      'The required parameters for this call are missing or invalid')
        regResult.set("PacketData", "errorContainer.0.fieldName", "displayName")

        if len(nuid) > 32:
            regResult.set("PacketData", "errorContainer.0.fieldError", "3")
            regResult.set("PacketData", "errorContainer.0.value", "TOO_LONG")
            logger_err.new_message("[Register] Email " + nuid + " is too long!", 1)
        else:
            regResult.set("PacketData", "errorContainer.0.fieldError", "2")
            regResult.set("PacketData", "errorContainer.0.value", "TOO_SHORT")
            logger_err.new_message("[Register] Email " + nuid + " is too short!", 1)
    elif db.checkIfEmailTaken(nuid):  # Email is already taken
        regResult.set("PacketData", "errorContainer.[]", "0")
        regResult.set("PacketData", "errorCode", "160")
        regResult.set("PacketData", "localizedMessage", 'That account name is already taken')
        logger_err.new_message("[Register] User with email " + nuid + " is already registered!", 1)
    elif timeNow.year - birthday.year - (
            (timeNow.month, timeNow.day) < (birthday.month, birthday.day)) < 18:  # New user is not old enough
        regResult.set("PacketData", "errorContainer.[]", "1")
        regResult.set("PacketData", "errorContainer.0.fieldName", "dob")
        regResult.set("PacketData", "errorContainer.0.fieldError", "15")
        regResult.set("PacketData", "errorCode", "21")
        logger_err.new_message("[Register] User with email " + nuid + " is too young to register new account!", 1)
    else:
        db.registerUser(nuid, password, str(birthday).split(" ")[0], country)
        logger.new_message("[Register] User " + nuid + " was registered successfully!", 1)

    Packet(regResult).sendPacket(self, "acct", 0x80000000, self.CONNOBJ.plasmaPacketID, logger=logger)
    self.CONNOBJ.plasmaPacketID += 1


def HandleNuLogin(self, data):
    """ User is logging in with email and password """

    loginResult = ConfigParser()
    loginResult.optionxform = str
    loginResult.add_section("PacketData")
    loginResult.set("PacketData", "TXN", "NuLogin")

    returnEncryptedInfo = int(
        data.get("PacketData", "returnEncryptedInfo"))  # If 1 - User wants to store login information

    try:
        nuid = data.get('PacketData', "nuid")
        password = data.get('PacketData', "password")
    except:
        encryptedInfo = data.get("PacketData", "encryptedInfo")

        encryptedLoginData = encryptedInfo.replace("Ciyvab0tregdVsBtboIpeChe4G6uzC1v5_-SIxmvSL", "")
        encryptedLoginData = encryptedLoginData.replace("-", "=").replace("_",
                                                                          "=")  # Bring string into proper format again

        loginData = b64decode(encryptedLoginData).split('\f')

        nuid = loginData[0]
        password = loginData[1]

    loginData = db.loginUser(nuid, password)

    if loginData['UserID'] > 0:  # Got UserID - Login Successful
        self.CONNOBJ.accountSessionKey = loginData['SessionID']
        self.CONNOBJ.userID = loginData['UserID']
        self.CONNOBJ.nuid = nuid

        loginResult.set("PacketData", "lkey", loginData['SessionID'])
        loginResult.set("PacketData", "nuid", nuid)

        if returnEncryptedInfo == 1:
            encryptedLoginData = "Ciyvab0tregdVsBtboIpeChe4G6uzC1v5_-SIxmvSL"

            encryptedLoginDataBuffer = b64encode(nuid)
            encryptedLoginDataBuffer += b64encode('\f')
            encryptedLoginDataBuffer += b64encode(password)

            pos = encryptedLoginDataBuffer.find("=")
            if pos is not -1:
                encryptedLoginDataBuffer[pos] = '-'

                pos = encryptedLoginDataBuffer.find("=")
                if pos is not -1:
                    encryptedLoginDataBuffer[pos] = '_'

            encryptedLoginData += encryptedLoginDataBuffer

            loginResult.set("PacketData", "encryptedLoginInfo", encryptedLoginData)

        loginResult.set("PacketData", "profileId", str(loginData['UserID']))
        loginResult.set("PacketData", "userId", str(loginData['UserID']))

        logger.new_message("[Login] User " + nuid + " logged in successfully!", 1)
    elif loginData['UserID'] == 0:  # The password the user specified is incorrect
        loginResult.set("PacketData", "localizedMessage", "The password the user specified is incorrect")
        loginResult.set("PacketData", "errorContainer.[]", "0")
        loginResult.set("PacketData", "errorCode", "122")

        logger_err.new_message("[Login] User " + nuid + " specified incorrect password!", 1)
    else:  # User not found
        loginResult.set("PacketData", "localizedMessage", "The user was not found")
        loginResult.set("PacketData", "errorContainer.[]", "0")
        loginResult.set("PacketData", "errorCode", "101")

        logger_err.new_message("[Login] User " + nuid + " does not exist", 1)

    Packet(loginResult).sendPacket(self, "acct", 0x80000000, self.CONNOBJ.plasmaPacketID, logger=logger)
    self.CONNOBJ.plasmaPacketID += 1


def HandleNuGetPersonas(self):
    """ Get personas associated with account """

    userID = self.CONNOBJ.userID
    personas = db.getUserPersonas(userID)

    personaList = ConfigParser()
    personaList.optionxform = str
    personaList.add_section("PacketData")
    personaList.set("PacketData", "TXN", "NuGetPersonas")
    personaList.set("PacketData", "personas.[]", str(len(personas)))

    personaId = 0
    for persona in personas:
        personaList.set("PacketData", "personas." + str(personaId), persona)
        personaId += 1

    Packet(personaList).sendPacket(self, "acct", 0x80000000, self.CONNOBJ.plasmaPacketID, logger=logger)
    self.CONNOBJ.plasmaPacketID += 1


def HandleNuLoginPersona(self, data):
    """ User logs in with selected Persona """

    personaLoginResult = ConfigParser()
    personaLoginResult.optionxform = str
    personaLoginResult.add_section("PacketData")
    personaLoginResult.set("PacketData", "TXN", "NuLoginPersona")

    requestedPersonaName = data.get("PacketData", "name")

    personaData = db.loginPersona(self.CONNOBJ.userID, requestedPersonaName)
    if personaData is not None:
        self.CONNOBJ.personaId = personaData['personaId']
        self.CONNOBJ.personaSessionKey = personaData['lkey']
        self.CONNOBJ.personaName = requestedPersonaName

        personaLoginResult.set("PacketData", "lkey", personaData['lkey'])
        personaLoginResult.set("PacketData", "profileId", str(self.CONNOBJ.personaId))
        personaLoginResult.set("PacketData", "userId", str(self.CONNOBJ.personaId))

        logger.new_message("[Persona] User " + self.CONNOBJ.nuid + " just logged as " + requestedPersonaName, 1)
    else:
        personaLoginResult.set("PacketData", "localizedMessage", "The user was not found")
        personaLoginResult.set("PacketData", "errorContainer.[]", "0")
        personaLoginResult.set("PacketData", "errorCode", "101")
        logger_err.new_message(
            "[Persona] User " + self.CONNOBJ.nuid + " wanted to login as " + requestedPersonaName + " but this persona cannot be found!",
            1)

    Packet(personaLoginResult).sendPacket(self, "acct", 0x80000000, self.CONNOBJ.plasmaPacketID, logger=logger)
    self.CONNOBJ.plasmaPacketID += 1


def HandleNuAddPersona(self, data):
    """ User wants to add a Persona """

    name = data.get("PacketData", "name")

    addPersonaResult = ConfigParser()
    addPersonaResult.optionxform = str
    addPersonaResult.add_section("PacketData")
    addPersonaResult.set("PacketData", "TXN", "NuAddPersona")

    if len(name) > 16 or len(name) < 3:  # Entered persona name length is out of bounds
        addPersonaResult.set("PacketData", "errorContainer.[]", "1")
        addPersonaResult.set("PacketData", "errorCode", "21")
        addPersonaResult.set("PacketData", "localizedMessage",
                             "The required parameters for this call are missing or invalid")
        addPersonaResult.set("PacketData", "errorContainer.0.fieldName", "displayName")

        if len(name) > 16:
            addPersonaResult.set("PacketData", "errorContainer.0.fieldError", "3")
            addPersonaResult.set("PacketData", "errorContainer.0.value", "TOO_LONG")
            logger_err.new_message(
                "[Persona] User " + self.CONNOBJ.nuid + " wanted to create new persona, but name " + name + " is too long!",
                1)
        else:
            addPersonaResult.set("PacketData", "errorContainer.0.fieldError", "2")
            addPersonaResult.set("PacketData", "errorContainer.0.value", "TOO_SHORT")
            logger_err.new_message(
                "[Persona] User " + self.CONNOBJ.nuid + " wanted to create new persona, but name " + name + " is too short!",
                1)
    elif db.checkIfPersonaNameExists(self.CONNOBJ.userID, name):
        addPersonaResult.set("PacketData", "errorContainer.[]", "0")
        addPersonaResult.set("PacketData", "localizedMessage", "That account name is already taken")
        addPersonaResult.set("PacketData", "errorCode", "160")
        logger_err.new_message(
            "[Persona] User " + self.CONNOBJ.nuid + " wanted to create new persona (" + name + "), but persona with this name is already registered in this account!",
            1)
    else:
        db.addPersona(self.CONNOBJ.userID, name)
        logger.new_message("[Persona] User " + self.CONNOBJ.nuid + " just created new persona (" + name + ")", 1)

    Packet(addPersonaResult).sendPacket(self, "acct", 0x80000000, self.CONNOBJ.plasmaPacketID, logger=logger)
    self.CONNOBJ.plasmaPacketID += 1


def HandleNuDisablePersona(self, data):
    """ User wants to remove a Persona """

    disablePersonaResult = ConfigParser()
    disablePersonaResult.optionxform = str
    disablePersonaResult.add_section("PacketData")
    disablePersonaResult.set("PacketData", "TXN", "NuDisablePersona")

    personaToDisable = data.get("PacketData", "name")

    if db.checkIfPersonaNameExists(self.CONNOBJ.userID, personaToDisable):
        db.removePersona(self.CONNOBJ.userID, personaToDisable)
        logger.new_message("[Persona] User " + self.CONNOBJ.nuid + " just removed persona (" + personaToDisable + ")",
                           1)
    else:
        disablePersonaResult.set("PacketData", "localizedMessage",
                                 "The data necessary for this transaction was not found")
        disablePersonaResult.set("PacketData", "errorContainer.[]", "0")
        disablePersonaResult.set("PacketData", "errorCode", "104")
        logger_err.new_message(
            "[Persona] User " + self.CONNOBJ.nuid + " wanted to remove persona (" + personaToDisable + "), but persona with this name didn't exist!",
            1)

    Packet(disablePersonaResult).sendPacket(self, "acct", 0x80000000, self.CONNOBJ.plasmaPacketID, logger=logger)
    self.CONNOBJ.plasmaPacketID += 1


def ReceivePacket(self, data, txn):
    if txn == 'GetCountryList':
        HandleGetCountryList(self)
    elif txn == 'NuGetTos':
        HandleNuGetTos(self)
    elif txn == 'NuAddAccount':
        HandleNuAddAccount(self, data)
    elif txn == 'NuLogin':
        HandleNuLogin(self, data)
    elif txn == 'NuGetPersonas':
        HandleNuGetPersonas(self)
    elif txn == 'NuLoginPersona':
        HandleNuLoginPersona(self, data)
    elif txn == 'NuAddPersona':
        HandleNuAddPersona(self, data)
    elif txn == 'NuDisablePersona':
        HandleNuDisablePersona(self, data)
    else:
        logger_err.new_message("[" + self.ip + ":" + str(self.port) + ']<-- Got unknown acct message (' + txn + ")", 2)
