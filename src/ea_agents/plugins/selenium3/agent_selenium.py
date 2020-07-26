#!/usr/bin/env python
# -*- coding: utf-8 -*-

# -------------------------------------------------------------------
# Copyright (c) 2010-2020 Denis Machard
# This file is part of the extensive automation project
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA
# -------------------------------------------------------------------

"""
Selenium3 agent
"""

from ea_agents import agent as GenericTool
from ea_agents.libs import settings as Settings

import logging
import sys
import subprocess
import threading
import os
import socket
import base64
import time

from urllib import request as requestlib
    
# disable system proxy for urllib, use only in localhost
proxy_handler = requestlib.ProxyHandler({})
opener = requestlib.build_opener(proxy_handler)
requestlib.install_opener(opener)

from selenium import webdriver

class WebdriverRemote(webdriver.Remote):
    def __init__(self, *args, **kwargs):
        """overwrite the class"""
        webdriver.Remote.__init__(self, *args, **kwargs)
    def start_session(self, *args, **kwargs):
        """overwrite and ignore start session"""
        return
    def execute(self, driver_command, params=None):
        """overwrite execute selenium command"""
        if self.session_id is not None:
            if not params:
                params = {'sessionId': self.session_id}
            elif 'sessionId' not in params:
                params['sessionId'] = self.session_id

        params = self._wrap_value(params)
        response = self.command_executor.execute(driver_command, params)
        if response:
            return response
        return {'success': 0, 'value': None, 'sessionId': self.session_id}

BIN_WIN = r'"%s\Plugins\selenium3\bin\selenium-script.bat" -jar ' % ( Settings.getDirExec() )
BIN_LINUX = "java \"%s/Plugins/selenium3/selenium-server-standalone.jar\"" % ( Settings.getDirExec() )

def initialize(*args, **kwargs):
    """Wrapper to initialize the object agent"""
    return SeleniumServer(*args, **kwargs)

class SeleniumServer(GenericTool.Tool):
    """selenium agent"""
    def __init__(self, controllerIp, controllerPort, toolName, 
                       toolDesc, defaultTool, supportProxy=0, 
                       proxyIp=None, proxyPort=None, sslSupport=True, 
                       seleniumIp="127.0.0.1", seleniumPort=4444):
        """selenium class"""
        GenericTool.Tool.__init__(self, controllerIp, controllerPort, 
                                  toolName, toolDesc, defaultTool, 
                                  supportProxy=supportProxy, proxyIp=proxyIp, 
                                  proxyPort=proxyPort, 
                                  sslSupport=sslSupport)
        # self.__type__ = __TYPE__
        self.__mutex__ = threading.RLock()
        self.toolName = toolName
        self.seleniumIp = seleniumIp
        self.seleniumPort = seleniumPort
        self.seleniumProcess = None
        
        self.urlHost = "http://%s:%s/wd/hub/" % (self.seleniumIp, self.seleniumPort)
             
    def checkPrerequisites(self):
        """Check prerequisites"""  
        # Adding limitation, blocking the run of several selenium server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        
        result = sock.connect_ex( (self.seleniumIp, self.seleniumPort))
        if result == 0:
            logging.error("Selenium Server already started in another instance!")
            raise Exception()
        
    def initAfterRegistration(self):
        """called after registration"""
        if self.seleniumProcess is not None:
            logging.debug("selenium server already started")
        else:
            self.startProcess()

    def onCleanup(self):
        """cleanup"""
        logging.info("stopping selenium server...")
        try:
            thread = threading.Thread(target = self.__stopProcess )
            thread.start()
            thread.join()   
        except Exception as e:
            logging.error( "unable to make a thread to stop process: %s" % e )
        
    def __stopProcess(self):
        """threaded function to stop the process"""
        if self.seleniumProcess is not None:
            logging.debug('killing process with pid %s' % self.seleniumProcess.pid)
            if sys.platform == "win32" :
                try:
                    logging.debug('killing process')
                    kill = subprocess.Popen( 
                                                r'taskkill /PID %s /F /T' % self.seleniumProcess.pid, 
                                                stdin=subprocess.PIPE, 
                                                stdout=subprocess.DEVNULL, 
                                                stderr=subprocess.STDOUT,
                                                shell=True
                                            )
                    kill.communicate()
                    kill.terminate()
                    kill.wait()
                    logging.debug('process killed')
                except Exception as e:
                    logging.error( "unable to kill the process: %s" % e )
            else:
                pass
   
            self.seleniumProcess.terminate()
            self.seleniumProcess.wait()
            
        logging.info("selenium server is stopped")
        
        # cleanup
        del self.seleniumProcess
        self.seleniumProcess = None
        
    def startProcess(self):
        """start selenium in a process"""
        logging.info("starting selenium server...")
        try:
            thread = threading.Thread(target = self.__startProcess )
            thread.start()
            thread.join()   
        except Exception as e:
            logging.error( "unable to make a thread to start process: %s" % e )
            
    def __startProcess(self, timeout=20):
        """threaded function to start the process"""
        try:
            if sys.platform == "win32" :
                __cmd__ = BIN_WIN
                __cmd__ += r' -Dwebdriver.chrome.driver="%s\plugins\selenium3\bin\chromedriver.exe" ' % (
                                                                                Settings.getDirExec()
                                                                                )
                __cmd__ += r' -Dwebdriver.gecko.driver="%s\plugins\selenium3\bin\geckodriver.exe" ' % (
                                                                                Settings.getDirExec()
                                                                                )
                __cmd__ += r' -Dwebdriver.edge.driver="%s\plugins\selenium3\bin\msedgedriver.exe" ' % (
                                                                                Settings.getDirExec()
                                                                                )
                                                                                
                __cmd__ +=  r' "%s\plugins\selenium3\bin\selenium-server-standalone.jar"' % (
                                                                                Settings.getDirExec()
                                                                                )
                #  -debug true
                __cmd__ += r' -log "%s\selenium3_%s.log"  -debug' % ( "%s\%s" % ( Settings.getDirExec(), 
                                                                                    Settings.get( 'Paths', 'logs' )), 
                                                                          self.toolName)
            else:
                __cmd__ = r'%s -log "%s/selenium_%s.log" -debug true' % (
                                                                            BIN_LINUX, 
                                                                            "%s\%s" % ( Settings.getDirExec(), 
                                                                                        Settings.get( 'Paths', 'logs' )),
                                                                            self.toolName
                                                                            )
            logging.debug( "external program called: %s" % __cmd__)

            self.seleniumProcess = subprocess.Popen(
                                                    __cmd__, 
                                                    stdin=subprocess.PIPE, 
                                                    stdout=subprocess.DEVNULL, 
                                                    stderr=subprocess.STDOUT,
                                                    shell=True 
                                                  )
            logging.debug("selenium server thread started pid=%s" % self.seleniumProcess.pid)

            # checking if the server is properly started
            currentTime = startedTime = time.time()
            started = False
            while((currentTime-startedTime)<timeout):
                try:
                    requestlib.urlopen(self.urlHost).read()
                except Exception as err:
                    currentTime = time.time()
                    time.sleep(2.0)
                    continue
                started = True
                break
            if not started:
                raise RuntimeError('start selenium java process failed!')
            else:
                time.sleep(2.0)
                logging.info("selenium server is started")

        except Exception as e:
            logging.error("unable to start selenium server: %s" % str(e))

    def onAgentNotify(self, client, tid, request):
        """Received a notify from server"""
        self.__mutex__.acquire()
        if request['uuid'] in self.context():
            if request['source-adapter'] in self.context()[request['uuid']]:
                a = self.context()[request['uuid']][request['source-adapter']]
                a.putItem( lambda: self.execAction(request) )
            else:
                logging.error("adapter context does not exists ScriptId=%s AdapterId=%s" % (request['uuid'], 
                                                                                        request['source-adapter'] ) )
        else:
            logging.error("Test context does not exits ScriptId=%s" % request['uuid'])
        self.__mutex__.release()

    def execAction(self, request):
        """
        Execute the action received from the server
        """
        # read the request
        waitUntil = False
        waitUntil_Timeout = 10.0
        waitUntil_Not = False
        waitUntil_Pool = 0.5
        waitUntil_Value = None
        
        # extract selenium data
        try:
            logging.debug('starting extract data for selenium')
            driver_command = request['data']['command-name']
            driver_params = request['data']['command-params']
            driver_capabilities = request['data']['command-capabilities']
            if 'sessionId' in driver_params:
                sessionId = driver_params['sessionId']
            else:
                sessionId = None
                
            if "wait-until" in request['data']:
                waitUntil = request['data']["wait-until"]
            if "wait-until-timeout" in request['data']: 
                waitUntil_Timeout = request['data']["wait-until-timeout"]
            if "wait-until-pool" in request['data']:
                waitUntil_Pool = request['data']["wait-until-pool"]
            if "wait-until-value" in request['data']: 
                waitUntil_Value = request['data']["wait-until-value"]
        except Exception as e:
            logging.error('unable to extract request from server: %s' % e )
            return
            
        # prepare id   
        try:
            globalId = "%s_%s_%s" % (request['script_id'], 
                                     request['source-adapter'], 
                                     request['data']['command-id'] )
            logging.debug( "<< %s #%s [%s %s %s]" % (request['data']['command-name'], 
                                                    globalId, 
                                                    waitUntil, 
                                                    waitUntil_Timeout, 
                                                    waitUntil_Value) )
        except Exception as e:
            logging.error('unable to read request: %s' % e )
            return
            
        # prepare driver for selenium
        try:
            logging.debug('preparing selenium driver')
            
            command_executor = 'http://%s:%s/wd/hub' % (self.seleniumIp, self.seleniumPort)
            seleniumDriver = WebdriverRemote(command_executor=command_executor)
            seleniumDriver.session_id = sessionId
            seleniumDriver.capabilities = driver_capabilities
        except Exception as e:
            logging.error('unable to prepare driver: %s' % e )
            self.sendError(request=request, data='unable to run selenium: %s' % e)
            return

        # execute the selenium command
        try:
            if waitUntil:
                end_time = time.time() + waitUntil_Timeout
                timeout_raised = False
                while True:
                    try:
                        response = seleniumDriver.execute(driver_command=driver_command, 
                                                          params=driver_params)
                        send_notify = False
                        if waitUntil_Value != None:
                            if response['status'] == 0 and response['value'] == waitUntil_Value:
                                send_notify = True
                        else:
                            if response['status'] == 0:
                                send_notify = True
                        
                        if send_notify:
                            data_notify = { 'command-name': request['data']['command-name'],
                                            'command-id': request['data']['command-id'],
                                            'command-value': response }
                            self.sendNotify( request=request, data=data_notify  )
                            break 
                    except Exception as e:
                        pass
                    time.sleep(waitUntil_Pool)
                    if time.time() > end_time:
                        timeout_raised = True
                        break
                        
                # timeout raised
                if timeout_raised:
                    data_notify = { 'command-name': request['data']['command-name'],
                                    'command-id': request['data']['command-id'],
                                    'command-value': {"status": 1000, 'value': None} }
                    self.sendNotify( request=request, data=data_notify  )
              

            else:

                    logging.debug('executing the selenium command %s with params %s' % (driver_command, driver_params) )
                    response = seleniumDriver.execute(driver_command=driver_command, 
                                                      params=driver_params)
                    logging.debug( ">> Action #%s terminated" % globalId )
                    
                    # remove image on error response
                    if response['status'] != 0: 
                        logging.error("error on selenium response - %s" % response)
                        if isinstance(response['value'], str):
                            if ',"screen":"' in response['value']:
                                begin, left = response['value'].split(',"screen":"')
                                junk, left = left.split('"', 1)
                                del junk
                                response['value'] = "%s%s" % (begin, left)
                                
                    # notify user
                    data_notify = { 'command-name': request['data']['command-name'],
                                    'command-id': request['data']['command-id'],
                                    'command-value': response }
                    self.sendNotify( request=request, data=data_notify  )  


                    # manually take screenshot
                    if driver_command == "screenshot":
                        logging.debug( "<< Uploading screenshot...")
                        extension = Settings.get( 'Screenshot', 'extension' )
                        fileName = "%s_%s_ADP%s_step%s_%s.%s" % (request['testcase-name'], 
                                                                 request['test-replay-id'], 
                                                                 request['source-adapter'], 
                                                                 request['data']['command-id'], 
                                                                 request['data']['command-name'], 
                                                                 extension.lower())
                        screenshot = base64.b64decode(response['value'].encode('ascii'))
                        self.uploadData(fileName=fileName,
                                        resultPath=request['result-path'], 
                                        data=screenshot)

                    logging.debug('executing the selenium command - terminated - notify sent')
        except Exception as e:
            logging.error('unable to execute action: %s' % e )
            self.sendError(request=request, data='unable to execute action: %s' % e)