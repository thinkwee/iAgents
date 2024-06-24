<p align="center">
  <img src='./static/github_cover.png' width=700>
</p>

<p align="center">
    【🚀 <a href="#⚡️-quickstart">Quickstart</a> | 📚 <a href="https://arxiv.org/abs/2406.14928">Paper</a> | 📖 <a href="wiki.md">Wiki</a> | 👥 <a href="friends">Interact with <i>Friends</i></a> | 🔬 <a href="#🔬-more-from-our-team")>More from our Team</a>】
</p>

## 📖 Overview

- **iAgents** is a platform **towards creating a world interwind by humans and agents**, where each human has a personal **agent** that can work on behalf the human to cooperate with other humans' agent. It is a new paradiam for [Large Language Model-powered Multi-Agent Systems](). **iAgents** proactively interact with human users to exchange information, while autonomously communicating with other agents to eliminate information asymmetry and collaborate effectively to accomplish tasks ([see our paper](https://arxiv.org/abs/2406.14928)).

<p align="center">
  <img src='./static/demo.png' width=1000>
</p>


## ⚡️ Quickstart

- **iAgents** feature an instant messaging web UI that users can utilize as a conventional chat application, with each user automatically equipped with a personal agent. Messages beginning with '@' are automatically transformed into collaborative task commands, prompting the agents of both chat participants to engage and resolve the task through autonomous communication.
- Here is a quick start to use **iAgents**. You need to prepare
   -  [Python environment of version 3.9 or higher](https://docs.anaconda.com/working-with-conda/environments/)
   -  [MySQL environment]()
   -  [OpenAI API key](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key)
- Then, follow these steps:
1. **Clone the GitHub Repository:** Begin by cloning the repository using the command:

   ```
   git clone https://github.com/thinkwee/iAgents.git
   ```

2. **Set Up Python Environment:** Ensure you have a version 3.9 or higher Python environment. You can create and
   activate this environment using the following commands, replacing `iAgents` with your preferred environment
   name:

   ```
   conda create -n iAgents python=3.9 -y
   conda activate iAgents
   ```

3. **Install Dependencies:** Move into the `iAgents` directory and install the necessary dependencies by running:

   ```
   cd iAgents
   pip3 install -r requirements.txt
   ```

4. **Set config file:** set your config file ``config/global.yaml`` by filling out
   -  backend.openai_api_key
   -  mysql.username
   -  mysql.password

   These are necessary parts for starting **iAgents**. Introduction for the full config file please see [here]()
5. **prepare your dataset** run the python script to create a mysql database for storing the messages, users, friendships and feedback tables in the **iAgents**
   ```
   python3 create_database.py
   ```

6. **Start!** simply by executing
   ```
   python3 app.py
   ```
   to start the IM UI of **iAgents**. Just invite your friend to register on the website, add them and chat with them! **Add @ before your message** and see what will happen!

## 🗺️ RoadMap
- [ ] Dockerfile
- [ ] Support uploading files as human user information source
- [ ] Fuzzy memory
- [ ] InfoNav visualizer
- [ ] Add more preset databases for experience
- [ ] Agent Cultivate

## 👨‍💻‍ Contributors

<a href="https://github.com/thinkwee/iAgents/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=thinkwee/iAgents" />
</a>

Made with [contrib.rocks](https://contrib.rocks).

## 🔎 Citation

```
@article{iagents,
      title = {Autonomous Agents for Collaborative Task under Information Asymmetry},
      author = {Wei Liu and Chenxi Wang and Yifei Wang and Zihao Xie and Rennai Qiu and Yufan Dang Zhuoyun Du and Weize Chen and Cheng Yang and Chen Qian},
      journal = {arXiv preprint arXiv:2406.14928},
      url = {https://arxiv.org/abs/2406.14928},
      year = {2024}
}
```

## ⚖️ License

- Source Code Licensing: Our project's source code is licensed under the Apache 2.0 License. This license permits the use, modification, and distribution of the code, subject to certain conditions outlined in the Apache 2.0 License.
- Data Licensing: The related data utilized in our project is licensed under CC BY-NC 4.0. This license explicitly permits non-commercial use of the data. We would like to emphasize that any models trained using these datasets should strictly adhere to the non-commercial usage restriction and should be employed exclusively for research purposes.

## 🔬 More from our Team
- We are [ChatDev](https://github.com/OpenBMB/ChatDev) team with a research focus on Large Language Model Multi-Agent Systems from [THUNLP Lab](https://github.com/thunlp) and [OpenBMB](https://github.com/openbmb). Our research can be found [here](https://thinkwee.top/multiagent_ebook/index.html#more-works), including
   -  Interaction and Communication among Agents
   -  Organization for Agents
   -  Evolvement for Agents
   -  Multi-Agent Systems for Simulation and Task-Solving

## 📬 Contact

If you have any questions, feedback, or would like to get in touch, please feel free to reach out to us via email at [qianc62@gmail.com](mailto:qianc62@gmail.com), [thinkwee2767@gmail.com](mailto:thinkwee2767@gmail.com)
