"""
File:        06_FetchingDataWhileCapturing.py

Description: This sample demonstrates how fetch data while a capture is in process using the 
             dSPACE XIL API server.

             This program uses the turn lamp simulation application from your demo directory
             MAPort\Common\SimulationApplications\<platform>. 

             Adapt lines 61-71 of this file according to your dSPACE platform.
 
             Make sure that the dSPACE platform that is used for this demo
             is registered with ControlDesk, AutomationDesk or the Platform Management API.

             Also note in the call to the method Configure of the MAPort, the second
             parameter is set to 'false'. This means that the specified simulation application
             will not be downloaded unless there is no application loaded on the platform. 
             If the specified application is already running, no further action will be taken. 
             If any other application is running on the platform, an exception will be thrown.

Tip/Remarks: Objects of some XIL API types (e.g., MAPort, Capture) must be disposed at the end
             of the function. We strongly recommend to use exception handling for this purpose
             to make sure that Dispose is called even in the case of an error.

Version:     4.0

Date:        May 2021

             dSPACE GmbH shall not be liable for errors contained herein or
             direct, indirect, special, incidental, or consequential damages
             in connection with the furnishing, performance, or use of this
             file.
             Brand names or product names are trademarks or registered
             trademarks of their respective companies or organizations.

Copyright 2021, dSPACE GmbH. All rights reserved.
"""


import json
import clr
import time

# for TCP/IP connection
import socket
import numpy as np
import struct
#from interface_functions import NeuralNetworkDecoder
import threading
from pathlib import Path

TCP_IP = "131.234.172.167" # IP Address of the workstation computer
TCP_PORT_DATA = 1030  #
TCP_PORT_WEIGHTS = 1031  #
BUFFER_SIZE = 988 # = floor(1024 // (measurement_size * 4)) * (measurement_size * 4) # <- 4 = nb of bits per float
b = bytes()  # byte container for dSPACE XIL API lists
# create socket and connect
data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP
weights_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP

clr.AddReference("System.Collections")
from System import Array
from System.Collections.Generic import Dictionary

# Load ASAM assemblies from the global assembly cache (GAC)
clr.AddReference(
    "ASAM.XIL.Implementation.TestbenchFactory, Version=2.1.0.0, Culture=neutral, PublicKeyToken=fc9d65855b27d387")
clr.AddReference("ASAM.XIL.Interfaces, Version=2.1.0.0, Culture=neutral, PublicKeyToken=bf471dff114ae984")

# Import XIL API .NET classes from the .NET assemblies
from ASAM.XIL.Implementation.TestbenchFactory.Testbench import TestbenchFactory
from ASAM.XIL.Interfaces.Testbench.Common.Error import TestbenchPortException
from ASAM.XIL.Interfaces.Testbench.Common.Capturing.Enum import CaptureState
from ASAM.XIL.Interfaces.Testbench.MAPort.Enum import MAPortState

# Import DemoHelpers for Python 3.9
from DemoHelpers import *

# The following lines must be adapted to the dSPACE platform used
# ------------------------------------------------------------------------------------------------
# Set IsMPApplication to true if you are using a multiprocessor platform
IsMPSystem = False


# Set the name of the task here (specified in the application's TRC file)
# Note: the default task name is "HostService" for PHS bus systems, "Periodic Task 1" for VEOS systems
#Task = "HostService"

Task = "ML_Expert_Main"  # Specified in the Data Capture Block in Simulink
# ------------------------------------------------------------------------------------------------


# ------------------------------------------------------------------------------------------------
# For multiprocessor platforms different tasknames and variable names have to be used.
# Some variables are part of the subappliaction "masterAppl", some belong to the 
# subapplication "slaveAppl"
# ------------------------------------------------------------------------------------------------
if IsMPSystem:
    masterTaskPrefix = "masterAppl/"
    slaveTaskPrefix = "slaveappl/"
    masterVariablesPrefix = "masterappl/Model Root/master/CentralLightEcu/"
    slaveVariablesPrefix = "slaveappl/Model Root/slave/FrontRearLightEcu/"

else:
    masterTaskPrefix = ""
    slaveTaskPrefix = ""
    masterVariablesPrefix = mvp = "DS1202 MicroLabBox()://Model Root"
    slaveVariablesPrefix = mvp

masterTask = f"{masterTaskPrefix}/{Task}" if masterTaskPrefix != "" else Task
slaveTask = f"{slaveTaskPrefix}/{Task}" if slaveTaskPrefix != "" else Task

# Use an MAPort configuration file that is suitable for your platform and simulation application
# See the folder Common\PortConfigurations for some predefined configuration files
MAPort_cfg_file = r"MAPortConfigDS1202.xml"



if __name__ == "__main__":
    # find config file
    MAPort_cfg_path = None
    for p in Path.cwd().glob("**/*"):
        if MAPort_cfg_file in str(p):
            MAPort_cfg_path = p
            print(f"Config file found at {MAPort_cfg_path}")
    if MAPort_cfg_path is None:
        raise FileNotFoundError(f"File {MAPort_cfg_file} not found")
    DemoCapture = None
    DemoMAPort = None

    try:
        # --------------------------------------------------------------------------
        # Create a TestbenchFactory object; the TestbenchFactory is needed to 
        # create the vendor-specific Testbench
        # --------------------------------------------------------------------------
        MyTestbenchFactory = TestbenchFactory()

        # --------------------------------------------------------------------------
        # Create a dSPACE Testbench object; the Testbench object is the central object to access
        # factory objects for the creation of all kinds of Testbench-specific objects
        # --------------------------------------------------------------------------
        MyTestbench = MyTestbenchFactory.CreateVendorSpecificTestbench("dSPACE GmbH", "XIL API", "2021-B")

        # --------------------------------------------------------------------------
        # We need an MAPortFactory to create an MAPort, a ValueFactory to create ValueContainer 
        # objects and also a CapturingFactory to create a CaptureResultMemoryWriter
        # The WatcherFactory is used to create a DurationWatcher and a ConditionWatcher,
        # the DurationFactory provides TimeSpanDuration objects.
        # --------------------------------------------------------------------------
        MyMAPortFactory = MyTestbench.MAPortFactory
        MyValueFactory = MyTestbench.ValueFactory
        MyCapturingFactory = MyTestbench.CapturingFactory
        MyWatcherFactory = MyTestbench.WatcherFactory
        MyDurationFactory = MyTestbench.DurationFactory
        # --------------------------------------------------------------------------
        # Create and configure an MAPort object and start the simulation
        # --------------------------------------------------------------------------
        print("Creating MAPort instance...", end='')
        # Create an MAPort object using the MAPortFactory
        DemoMAPort = MyMAPortFactory.CreateMAPort("DemoMAPort")
        print("...done.")
        # Load the MAPort configuration
        print("Configuring MAPort...", end='')
        DemoMAPortConfig = DemoMAPort.LoadConfiguration(str(MAPort_cfg_path))
        # Apply the MAPort configuration
        DemoMAPort.Configure(DemoMAPortConfig, False)
        print("...done.")
        if DemoMAPort.State != MAPortState.eSIMULATION_RUNNING:
            # Start the simulation
            print("Starting simulation...", end='')
            DemoMAPort.StartSimulation()
            print("...done.")

        # ----------------------------------------------------------------------
        # Define the variables to be captured
        # ----------------------------------------------------------------------
        # Info: Available variables can be read out with DemoMAPort.VariableNames
        start_var = f"{mvp}/Start/start"
        i_d_soll = f"{mvp}/I_d_soll/Out1"
        i_q_soll = f"{mvp}/I_q_soll/Out1"
        i_d_ist = f"{mvp}/I_dq/I_d_ist"
        i_q_ist = f"{mvp}/I_dq/I_q_ist"
        var_capture_l = [i_d_soll, i_q_soll, i_d_ist, i_q_ist] 

        # --------------------------------------------------------------------------
        # Create and initialize Capture object
        # --------------------------------------------------------------------------
        print("Creating Capture...", end='')
        DemoCapture = DemoMAPort.CreateCapture(masterTask)
        DemoCapture.Variables = Array[str](var_capture_l)

        # In this demo a higher downsampling is used to reduce the number of captured data samples
        # Only every 20th measured sample is captured
        DemoCapture.Downsampling = 1
        print("...done.")

        # --------------------------------------------------------------------------
        # Create one ConditionWatcher and one DurationWatcher and set start- and stop triggers
        # --------------------------------------------------------------------------
        # Create Defines for ConditionWatchers
        DemoDefines = Dictionary[str, str]()
        DemoDefines.Add('CaptureTrigger', start_var)

        # Negative Delay: Start Capturing 0.1s before StartTriggerCondition is met
        StartDelay = MyDurationFactory.CreateTimeSpanDuration(0.0)
        print("Creating ConditionWatcher...", end='')
        DemoStartWatcher = MyWatcherFactory.CreateConditionWatcher("posedge(CaptureTrigger,0.5)", DemoDefines)
        DemoCapture.SetStartTrigger(DemoStartWatcher, StartDelay)
        print("...done.")

        print("Creating DurationWatcher...", end="")
        StopDelay = MyDurationFactory.CreateTimeSpanDuration(0)
        captureTime = 1
        DemoStopWatcher = MyWatcherFactory.CreateConditionWatcher("negedge(CaptureTrigger,0.5)", DemoDefines)
        #DemoStopWatcher = MyWatcherFactory.CreateDurationWatcherByTimeSpan(captureTime)
        DemoCapture.SetStopTrigger(DemoStopWatcher, StopDelay)
        print("...done.")

        # --------------------------------------------------------------------------
        # Create CaptureResultMemoryWriter object
        # --------------------------------------------------------------------------
        print("Creating CaptureResultMemoryWriter...", end='')
        DemoCaptureWriter = MyCapturingFactory.CreateCaptureResultMemoryWriter()
        print("...done.")

        # --------------------------------------------------------------------------
        # Declare a CaptureResult 
        # --------------------------------------------------------------------------
        DemoCaptureResult = MyCapturingFactory.CreateCaptureResult()

        # --------------------------------------------------------------------------
        # Capturing process
        # --------------------------------------------------------------------------
        print("\nStart capturing.")
        DemoCapture.Start(DemoCaptureWriter)

        # establish socket for TCP/IP
        #data_socket.connect((TCP_IP, TCP_PORT_DATA))
        # weights_socket.connect((TCP_IP, TCP_PORT_WEIGHTS))

        time.sleep(2.0)

        ### This part is only relevant if we want so send network weights to the MLB

        # print("Receiving architecture from remote RL server")
        # binary_architecture = weights_socket.recv(1024)
        # architecture = np.frombuffer(binary_architecture, dtype=np.float32)
        # experiment_name = "experiment_path"
        # print(experiment_name)
        # nn_decoder = NeuralNetworkDecoder(experiment_name=experiment_name,
        #                                   architecture=architecture)
        # nn_parameter_paths = []
        # for _i in range(nn_decoder.nb_dense_layers):
        #     nn_parameter_paths.append(masterVariablesPrefix + "Control_Scheme/Reconfigure_Network/Subsystem/w" + str(_i) + "/Value")
        #     #nn_parameter_paths.append(masterVariablesPrefix + "Controller/Subsystem/w" + str(_i) + "/Value")
        # print(nn_parameter_paths)

        # print("Receiving parameters from remote RL server")
        # weights = nn_decoder.recv_first_network(weights_socket)

        # time.sleep(2.0)

        # print("Receiving initialized learning_rate")
        # learning_rate = np.frombuffer(weights_socket.recv(4), dtype=np.float32)[0]

        # print("Initializing network on MicroLabBox")
        # for _i in range(nn_decoder.nb_dense_layers):
        #     w = np.transpose(np.append(weights[_i * 2], [weights[_i * 2 + 1]], axis=0))
        #     w_shape = np.shape(w)
        #     if _i == 0:
        #         w = np.append(w, np.zeros([w_shape[0], nn_decoder.nb_neurons_per_layer + 1 - w_shape[1]]), axis=1)
        #     else:
        #         w = np.append(w, np.zeros([nn_decoder.nb_neurons_per_layer - w_shape[0], w_shape[1]]), axis=0)

        #     DemoMAPort.Write(
        #         nn_parameter_paths[_i],
        #         MyValueFactory.CreateFloatMatrixValue(
        #         Array[Array[float]](w.tolist())
        #         )
        #     )

        ### End

        # DemoMAPort.Write(
        #     learningRate,
        #     MyValueFactory.CreateFloatValue(learning_rate)
        # )

        print("Waiting until Capture is running...")
        while DemoCapture.State != CaptureState.eRUNNING:
            time.sleep(0.02)
        print("Starting to fetch data...\n")

        # While the Capture is running, data is fetched in intervals.
        # this data can be worked with while the capturing continues.
        # In case of this demo it is just printed into the console
        capture_count = 0
        print("STARTING")
        # weights_socket.send(bytes(1))
        # threading.Thread(target=nn_decoder.network_acquisition,
        #                  args=(weights_socket, DemoMAPort, nn_parameter_paths, updateTime, MyValueFactory,)).start()
        # threading.Thread(target=nn_decoder.input_parser, args=()).start()

        def extract_value(captured_result, var_lbl):
            x = captured_result.ExtractSignalValue(slaveTask, var_lbl)
            return convertIBaseValue(x.FcnValues).Value

        while DemoCapture.State != CaptureState.eFINISHED:
            # time.sleep(0.00004) # sleep is for the weak
            demo_captured_result = DemoCapture.Fetch(False)
            # nn_decoder.pipeline_active = False

            # --------------------------------------------------------------------------
            # Extract measured data from CaptureResult
            # --------------------------------------------------------------------------

            fetched_signals_arr = np.array([extract_value(demo_captured_result, s) for s in var_capture_l],
                                            dtype=np.float32).T

            # --------------------------------------------------------------------------
            # Write the fetched data samples into the console window
            # --------------------------------------------------------------------------

            # For MP applications, the number of samples fetched by the masterApplication and the slaveApplication may be different.
            # To avoid IndexOutOfBounds errors, the lower value for NSamples is used. For single processor platforms, both values are the same.
            for row in fetched_signals_arr:
                # convert float array to bytes
                b = row.tobytes()
                # send bytes
                if (len(b) <= BUFFER_SIZE):
                    data_socket.send(b)
                else:
                    for i in range(0, len(b) // BUFFER_SIZE):
                        data_socket.send(b[i * BUFFER_SIZE:(i + 1) * BUFFER_SIZE])

                    if len(b) > ((i + 1) * BUFFER_SIZE):
                        data_socket.send(b[(i + 1) * BUFFER_SIZE:])

            capture_count += 1

        data_socket.close()
        weights_socket.close()
        print("Capturing finished.\n")
        # nn_decoder.pipeline_active = False

        #print("Setting Trigger to 0.0 (off)\n")
        #DemoMAPort.Write(manualCaptureTrigger, MyValueFactory.CreateFloatValue(0.0))

        # print("")
        # print("Demo successfully finished!\n")
        # nn_decoder.pipeline_active = False
        # time.sleep(0.2)
        # DemoMAPort.Write(
        #     updateTime,
        #     MyValueFactory.CreateFloatValue(np.finfo(float).max)
        # )


    except TestbenchPortException as ex:
        # -----------------------------------------------------------------------
        # Display the vendor code description to get the cause of an error
        # -----------------------------------------------------------------------
        print("A TestbenchPortException occurred:")
        print("CodeDescription: %s" % ex.CodeDescription)
        print("VendorCodeDescription: %s" % ex.VendorCodeDescription)
        raise
    finally:
        # -----------------------------------------------------------------------
        # Attention: make sure to dispose the Capture object and the MAPort object in any case to free
        # system resources like allocated memory and also resources and services on the platform
        # -----------------------------------------------------------------------

        if DemoCapture != None:
            DemoCapture.Dispose()
            DemoCapture = None
        if DemoMAPort != None:
            DemoMAPort.Dispose()
            DemoMAPort = None
