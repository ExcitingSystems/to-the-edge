"""This script runs the RemoteDDPGAgent on the workstation."""

import threading

import numpy as np
import torch
import torch.nn as nn
from remote_nc import RemoteDynamicComposite
from utils.baseline_foc import ClassicController
from utils.env import FastPMSM
from utils.topology import ControlledPMSM, DynamicComposite, ACTIVATION_FUNCS
from utils.data_storage import DataPaths
from utils.experiment import get_reference_data


# Init Connection, NC and Internal Model

# Start Connection
# -> Check if connection is stable
###
# Learn SysID Model
# -> Store sended data till one batch is filled up
# --> [I_d, I_q, Idx] (Ground Trouth)
# -> Run simulation
# --> Internalmodel is controlled by PI controller
# --> Produces diffrentiable trajectory
# --> GT and DT are used to compute gradient
# --> Update prameter models
###
# Train NC
# -> NC acting on the learned internal model
# -> Target should be given by an PI controller
# -> Try to follow reference signal
# --> Reference should keept constant


def input_parser(*objects_to_close):
    msg = ''
    while msg != 'c':
        msg = input()
        print(msg)
    for close in objects_to_close:
        close.close()


if __name__ == '__main__':
    # tf.compat.v1.disable_eager_execution() #? needed? y/n?

    mode = "SysID"

    address = "131.234.172.184"  # IP address of this workstation

    # nb_actions = 8
    observation_length = 2
    window_length = 1

    saturated_mode = False
    batch_size = 64

    # Parameters for reference loading
    n_ref_trajectories = 110_000
    episode_len = 201
    load_data = True

    # Load same references
    device = torch.device('cpu')
    dp = DataPaths()
    x_star = get_reference_data(
        load_data, dp.REF_DATA_PATH, n_ref_trajectories, episode_len, device)

    # Time span
    ts = 1e-4  # env.physical_system.tau
    t0, tf = 0, 0.02  # initial and final time for controlling the system
    t = torch.arange(t0, tf+ts, ts).to(device, dtype=torch.float32)

    # create env for easy access to the parameters; env itself is not in use
    env = FastPMSM(x_star=x_star.cpu().numpy(),
                   batch_size=batch_size, saturated=saturated_mode)

    internal_model = ControlledPMSM(t, env.me_omega,
                                    saturated=saturated_mode,
                                    is_general_system=False).to(device)

    # Choose controller
    if mode == "SysID":
        cntrl_mdl = ClassicController(env, batch_size)
    else:
        cntrl_mdl = nn.Sequential(nn.Linear(DynamicComposite.n_input_fe(), 225), ACTIVATION_FUNCS.get('sinus')(),
                                  nn.Linear(225, 113), nn.ReLU(),
                                  nn.Linear(113, DynamicComposite.N_OUTPUT)).to(device)

    agent = RemoteDynamicComposite(
        # pipeline parameters
        address=address,
        data_port=1030,
        weights_port=1031,
        observation_length=observation_length,
        model=internal_model,
        step_offset=0,

        # agent parameters
        t=t,
        cntrl_mdl=cntrl_mdl,
        int_mdl=internal_model,
        x_star=x_star
    )

    threading.Thread(target=input_parser, args=(agent,)).start()  # needed?
    agent.start(verbose=2)
