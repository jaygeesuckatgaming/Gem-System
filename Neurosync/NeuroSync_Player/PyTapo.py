from pytapo import Tapo

user = "jaygee" # user you set in Advanced Settings -> Camera Account
password = "1248aceg" # password you set in Advanced Settings -> Camera Account
host = "192.168.1.100" # ip of the camera, example: 192.168.1.52

tapo = Tapo(host, user, password)

print(tapo.getBasicInfo())