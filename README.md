# Slackbot with bolt in socket mode

## Building docker image

```
docker build -t slackbot docker
```

## Running docker container

```
docker run -ti --env-file slack.env -v $(pwd)/config.yaml:/config.yaml slackbot slackbot-socket-bolt.py /config.yaml
```
