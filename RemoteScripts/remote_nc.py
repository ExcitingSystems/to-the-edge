from 

class RemoteDynamicComposite(DynamicComposite):
    def __init__(self,
                 address=None,
                 data_port=1030,
                 weights_port=1031,
                 observation_length=None,
                 weights_path=None,
                 step_offset=0,
                 optimizer=None,
                 learning_rate=0,
                 **kwargs):
        """
        Args:
            address(str): IP-address of this host
            port(int): Port for the connection
            weights(path): Path for initial weights to load. Also if a name is passed the weights are saved after each
                            training episode with the same name. Don not add .h5 at the end.
            max_recording_length(int): Maximum number of steps of one recording. All experiences that exceed this number
                                       of steps will be ignored
            weights_save_interval: Number of training steps after the weights should be saved with the ending of number
                                    of iterations. This is done after training an episode and the value should be larger
                                    than the max_recording_length.
            step_offset: if the learning is continued on a pre-trained agent this value is the number of pre-trained
                        steps to get the correct number of training steps
            kwargs: Further arguments of the superclass DQNAgent
        """
        super().__init__(**kwargs)