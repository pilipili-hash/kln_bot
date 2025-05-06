# 可琳雫,一个基于ncatbot的可爱机器人

## 功能:

​	大致功能正在做有这些:

![menu](/img/menu.png)

发送/帮助 带上前面的序号有详细帮助说明。

安装方法:

首先git代码:

```
git clone https://github.com/pilipili-hash/kln_bot.git
```

然后进入目录：

```
cd kln_bot
```

```
python -m venv kln_bot
```

```
.\kln_bot\Scripts\activate
```

```
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple
```

```
pip install -r requirements.txt
```

```
在main.py填入qq和端口之后
python main.py
```

如何获取pixiv_token，见[pixiv seems not allowing username/password login now · Issue #158 · upbit/pixivpy](https://github.com/upbit/pixivpy/issues/158#issuecomment-778919084)