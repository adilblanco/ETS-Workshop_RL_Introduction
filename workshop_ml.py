{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import os\n",
    "import torch\n",
    "import torch.nn as nn\n",
    "import torch.multiprocessing as mp\n",
    "\n",
    "import gym\n",
    "import json\n",
    "import shutil\n",
    "\n",
    "import numpy as np\n",
    "\n",
    "from collections import deque\n",
    "from itertools import product, permutations\n",
    "\n",
    "num_processes = 2\n",
    "\n",
    "N_EPOCH = 264000 // num_processes\n",
    "\n",
    "obs_dim = 128 * 4\n",
    "actions_dim = 4 - 1\n",
    "hidden_size = 128\n",
    "\n",
    "seed = 42"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "class ActorModel(nn.Module):\n",
    "    def __init__(self, obs_shape, action_space, hidden_size):\n",
    "        super(ActorModel, self).__init__()\n",
    "        self.model = nn.Sequential(\n",
    "            nn.Linear(obs_shape, hidden_size), nn.Tanh(),\n",
    "            nn.Linear(hidden_size, hidden_size // 2), nn.Tanh(),\n",
    "            nn.Linear(hidden_size // 2, hidden_size // 4), nn.Tanh(),\n",
    "            nn.Linear(hidden_size // 4, action_space), nn.Softmax(dim=0))\n",
    "\n",
    "        for m in self.model:\n",
    "            if isinstance(m, nn.Linear):\n",
    "                nn.init.constant_(m.weight, 0)\n",
    "                nn.init.constant_(m.bias, 1)\n",
    "\n",
    "        self.train()\n",
    "\n",
    "    def forward(self, inputs):\n",
    "        return self.model(inputs)\n",
    "\n",
    "    def create_eligibility_traces(self, device=None):\n",
    "        if device is None:\n",
    "            device = torch.device('cpu')\n",
    "        traces = []\n",
    "        with torch.no_grad():\n",
    "            for param in self.model.parameters():\n",
    "                traces.append(\n",
    "                    param.data.new_zeros(param.data.size()).to(device))\n",
    "        return traces"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "class CriticModel(nn.Module):\n",
    "    def __init__(self, obs_shape, hidden_size):\n",
    "        super(CriticModel, self).__init__()\n",
    "        self.model = nn.Sequential(\n",
    "            nn.Linear(obs_shape, hidden_size), nn.Tanh(),\n",
    "            nn.Linear(hidden_size, hidden_size // 2), nn.Tanh(),\n",
    "            nn.Linear(hidden_size // 2, hidden_size // 4), nn.Tanh(),\n",
    "            nn.Linear(hidden_size // 4, 1))\n",
    "\n",
    "        for m in self.model:\n",
    "            if isinstance(m, nn.Linear):\n",
    "                nn.init.constant_(m.weight, 0)\n",
    "                nn.init.constant_(m.bias, 1)\n",
    "\n",
    "\n",
    "        self.eligibility_traces = []\n",
    "\n",
    "        self.train()\n",
    "\n",
    "    def forward(self, inputs):\n",
    "        return self.model(inputs)\n",
    "\n",
    "    def create_eligibility_traces(self, device=None):\n",
    "        if device is None:\n",
    "            device = torch.device('cpu')\n",
    "        traces = []\n",
    "        with torch.no_grad():\n",
    "            for param in self.model.parameters():\n",
    "                traces.append(\n",
    "                    param.data.new_zeros(param.data.size()).to(device))\n",
    "        return traces"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "def update_state(ram_bytes, device=None):\n",
    "    if device is None:\n",
    "        device = torch.device(\"cpu\")\n",
    "\n",
    "    update_state.frames_buffer\n",
    "    frame = ram_bytes / torch.Tensor([255.0]).to(device)\n",
    "    if update_state.frames_buffer is None:\n",
    "        update_state.frames_buffer = deque([torch.zeros(frame.size()).to(device)] * 4, maxlen=4)\n",
    "    update_state.frames_buffer.appendleft(frame)\n",
    "    return torch.stack(list(update_state.frames_buffer)).flatten().to(device)\n",
    "update_state.frames_buffer = None\n",
    "\n",
    "def save_checkpoint(state, is_best, filename='checkpoint_a.pth.tar'):\n",
    "    torch.save(state, filename)\n",
    "    if is_best:\n",
    "        shutil.copyfile(filename, 'model_best.pth.tar')\n",
    "\n",
    "\n",
    "def cosine_annealing_eps(epoch, eps_min, eps_max, epoch_max, device=None):\n",
    "    if device is None:\n",
    "        device = torch.device('cpu')\n",
    "    return torch.Tensor([eps_min + 0.5 * (eps_max - eps_min) * (1 + np.cos(epoch / epoch_max * np.pi))]\n",
    "                        ).to(device=device, dtype=torch.float)\n",
    "\n",
    "\n",
    "def cosine_annealing_lr(epoch, lr_min, lr_max, epoch_max, device=None):\n",
    "    if device is None:\n",
    "        device = torch.device('cpu')\n",
    "    return torch.Tensor([lr_min + 0.5 * (lr_max - lr_min) * (1 + np.cos(epoch/epoch_max * np.pi))]).to(device=device, dtype=torch.float)\n",
    "\n",
    "\n",
    "def load_actor_critic(filename, actor_model, critic_model):\n",
    "    print(\"=> loading checkpoint '{}'\".format(filename))\n",
    "    if os.path.isfile(filename):\n",
    "        checkpoint = torch.load(filename)\n",
    "        actor_model.load_state_dict(checkpoint['actor_dict'])\n",
    "        critic_model.load_state_dict(checkpoint['critic_dict'])\n",
    "        return checkpoint['iteration_number']\n",
    "    else:\n",
    "        print(\"=> no checkpoint found at '{}'\".format(filename))\n",
    "\n",
    "\n",
    "def uniform_interval_random_sampling(start, end, step_in_between):\n",
    "    intervals = [start - (start - end) / step_in_between * _ for _ in range(step_in_between + 1)]\n",
    "    intervals_pairs = list(zip(intervals[:-1], intervals[1:]))\n",
    "    sampling = [start] + [np.random.uniform(_, __) for _, __ in intervals_pairs] + [end]\n",
    "    return sampling\n",
    "\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "def train(*args):\n",
    "    args = args[0]\n",
    "    rank = args[0]\n",
    "    actor_model = args[1]\n",
    "    critic_model = args[2]\n",
    "    iteration_number = args[3]\n",
    "    gamma = args[4]\n",
    "    lamda_actor = args[5]\n",
    "    lamda_critic = args[6]\n",
    "    alpha_actor = args[7]\n",
    "    alpha_critic = args[8]\n",
    "    save_models = args[9]\n",
    "\n",
    "    env = gym.make('Breakout-ram-v4')\n",
    "\n",
    "    torch.manual_seed(seed + rank)\n",
    "\n",
    "    ln = torch.log\n",
    "\n",
    "    total_score = 0\n",
    "\n",
    "    for epoch in range(N_EPOCH):\n",
    "        frame = env.reset()\n",
    "        reset_state(frame)\n",
    "        frame = torch.from_numpy(frame).to(device).to(torch.float)\n",
    "\n",
    "        actor_eligibility_traces = actor_model.create_eligibility_traces()\n",
    "        critic_eligibility_traces = critic_model.create_eligibility_traces()\n",
    "\n",
    "\n",
    "        I = 1\n",
    "        real_score = 0\n",
    "        lr_actor = cosine_annealing_lr(epoch, lr_min=0.0000001, lr_max=alpha_actor, epoch_max=N_EPOCH)\n",
    "        lr_critic = cosine_annealing_lr(epoch, lr_min=0.0000001, lr_max=alpha_critic, epoch_max=N_EPOCH)\n",
    "        while True:\n",
    "\n",
    "            last_frame = frame\n",
    "            frame, reward, is_done, infos = env.step(1)\n",
    "            frame = torch.from_numpy(frame).to(device).to(torch.float)\n",
    "\n",
    "            state = update_state(frame - last_frame)\n",
    "            lives = infos['ale.lives']\n",
    "\n",
    "            while infos['ale.lives'] == lives and not is_done:\n",
    "                policy = actor_model(state)\n",
    "                action_probs = policy.detach().numpy()\n",
    "                if (rank < 2):\n",
    "                    action = np.random.choice(range(actions_dim), p=action_probs)\n",
    "                else:\n",
    "                    action = np.argmax(action_probs)\n",
    "                    \n",
    "                env.render()\n",
    "\n",
    "                one_hot = torch.zeros(action_probs.shape)\n",
    "                one_hot[action] = policy[action]\n",
    "\n",
    "                ln_policy = ln(policy)\n",
    "\n",
    "                if action > 0:\n",
    "                    action += 1\n",
    "\n",
    "                last_frame = frame\n",
    "                frame, reward, is_done, infos = env.step(action)\n",
    "                frame = torch.from_numpy(frame).to(device).to(torch.float)\n",
    "                next_state = update_state(frame - last_frame)\n",
    "\n",
    "                real_score += reward\n",
    "\n",
    "                if infos['ale.lives'] != lives:\n",
    "                    reward = -1\n",
    "\n",
    "                if is_done:\n",
    "                    assert True\n",
    "\n",
    "                if infos['ale.lives'] != lives:\n",
    "                    next_state_value = torch.Tensor([0])\n",
    "                    total_score += real_score\n",
    "                else:\n",
    "                    with torch.no_grad():\n",
    "                        next_state_value = critic_model(next_state)\n",
    "\n",
    "                current_state_value = critic_model(state)\n",
    "\n",
    "                delta = reward + gamma * next_state_value - current_state_value\n",
    "\n",
    "                actor_model.zero_grad()\n",
    "                critic_model.zero_grad()\n",
    "                delta.backward()\n",
    "                ln_policy.backward(one_hot)\n",
    "\n",
    "                with torch.no_grad():\n",
    "                    actor_params = list(actor_model.parameters())\n",
    "                    critic_params = list(critic_model.parameters())\n",
    "                    for i in range(len(critic_params)):\n",
    "                        updated_trace = gamma * lamda_actor * critic_eligibility_traces[i] + critic_params[i].grad.data\n",
    "                        critic_eligibility_traces[i] = updated_trace\n",
    "                        regularized = (1 - critic_params[i].data.norm(2) * 0.1) * critic_params[i].data\n",
    "                        updated = regularized + lr_critic * delta * critic_eligibility_traces[i].data\n",
    "                        critic_params[i].data = updated\n",
    "                        assert True\n",
    "\n",
    "                    for i in range(len(actor_params)):\n",
    "                        updated_trace = gamma * lamda_actor * actor_eligibility_traces[i].data + I * actor_params[i].grad.data\n",
    "                        actor_eligibility_traces[i].data = updated_trace\n",
    "                        regularized = (1 - actor_params[i].data.norm(2) * 0.1) * actor_params[i].data\n",
    "                        updated = regularized + lr_actor * delta * actor_eligibility_traces[i].data\n",
    "                        actor_params[i].data = updated\n",
    "                        assert True\n",
    "\n",
    "                I = gamma * I\n",
    "                state = next_state\n",
    "\n",
    "            if is_done:\n",
    "                save_model(rank, epoch, real_score, iteration_number, save_models, actor_model, critic_model)\n",
    "                break\n",
    "\n",
    "    print(json.dumps({'gamma': gamma, 'lambda_actor': lamda_actor, 'lambda_critic': lamda_critic , 'rank': rank, 'total_score': total_score, 'total_score_per_epoch': total_score / N_EPOCH, 'total_score_per_epoch_per_live': total_score / N_EPOCH / 5}) + ',')\n",
    "\n",
    "def save_model(rank, epoch, real_score, iteration_number, save_models, actor_model, critic_model):\n",
    "    print('[proc{}:epoch{}] Score: {}'.format(\n",
    "        rank, epoch, real_score))\n",
    "    if save_models and epoch % 10 == 0 and epoch > 0:\n",
    "        fname = \"saved_checkpoint_{}_{}.pth.tar\".format(\n",
    "            epoch, iteration_number)\n",
    "        print(fname)\n",
    "        save_checkpoint({\n",
    "            'iteration_number': iteration_number + 1,\n",
    "            'actor_dict': actor_model.state_dict(),\n",
    "            'critic_dict': critic_model.state_dict()\n",
    "        }, False, filename=fname)\n",
    "\n",
    "def reset_state(frame):\n",
    "    update_state(torch.from_numpy(np.zeros(frame.shape)).to(device).to(torch.float))\n",
    "    update_state(torch.from_numpy(np.zeros(frame.shape)).to(device).to(torch.float))\n",
    "    update_state(torch.from_numpy(np.zeros(frame.shape)).to(device).to(torch.float))\n",
    "    update_state(torch.from_numpy(np.zeros(frame.shape)).to(device).to(torch.float))\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "torch.manual_seed(seed)\n",
    "\n",
    "dtype = torch.float\n",
    "device = torch.device(\"cpu\")\n",
    "# device = torch.device(\"cuda:0\") # Uncomment this to run on GPU\n",
    "\n",
    "gamma_sampling = uniform_interval_random_sampling(0.01, 0.9999, 20)\n",
    "lambda_actor_sampling = uniform_interval_random_sampling(0.1, 0.9, 20)\n",
    "lambda_critic_sampling = uniform_interval_random_sampling(0.1, 0.9, 20)\n",
    "\n",
    "GAMMA = 0.9\n",
    "ALPHA_ACTOR = 0.0025\n",
    "ALPHA_CRITIC = 0.0025\n",
    "\n",
    "hyperparams_triples = list(product(gamma_sampling, lambda_actor_sampling, lambda_critic_sampling))\n",
    "np.random.shuffle(hyperparams_triples)\n",
    "\n",
    "\n",
    "for gamma, lamda_actor, lamda_critic in hyperparams_triples:\n",
    "    iteration_number = 0\n",
    "\n",
    "    actor = ActorModel(obs_dim, actions_dim, hidden_size)\n",
    "    actor.to(device=device, dtype=dtype)\n",
    "\n",
    "    critic = CriticModel(obs_dim, hidden_size)\n",
    "    critic.to(device=device, dtype=dtype)\n",
    "\n",
    "    actor.share_memory()\n",
    "    critic.share_memory()\n",
    "\n",
    "    with mp.Pool(processes=num_processes) as pool:\n",
    "        args = [(rank, actor, critic, iteration_number,\n",
    "                 gamma, lamda_actor, lamda_critic, ALPHA_ACTOR, ALPHA_CRITIC, rank == 0) for rank in range(num_processes)]\n",
    "        pool.map(train, args)"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.7.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}