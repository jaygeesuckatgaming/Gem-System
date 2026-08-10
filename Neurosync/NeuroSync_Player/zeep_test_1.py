from zeep import Client
from zeep.wsse.username import UsernameToken

ptz_wsdl = "D:\Projects\camera\zeep\wsdl\ptz.wsdl"
media_wsdl = "D:\Projects\camera\zeep\wsdl\media.wsdl"

ip = "192.168.1.100"
port = "2020"
username = "jaygee"
password = "1248aceg"

xaddr = "http://"+ip+":"+port+"/onvif/ptz_service"

media_client = Client(wsdl=media_wsdl, wsse=UsernameToken(
    username, password, use_digest=True))
media = media_client.create_service(
    "{http://www.onvif.org/ver10/media/wsdl}MediaBinding", xaddr)

ptz_client = Client(wsdl=ptz_wsdl, wsse=UsernameToken(
    username, password, use_digest=True))
ptz = ptz_client.create_service(
    "{http://www.onvif.org/ver20/ptz/wsdl}PTZBinding", xaddr)

profile = media.GetProfiles()[0]

ptz_config = ptz.GetConfigurationOptions(profile.PTZConfiguration.token)

velocity = {
    "PanTilt": {
        "x": ptz_config.Spaces.ContinuousPanTiltVelocitySpace[0].XRange.Min,
        "y": ptz_config.Spaces.ContinuousPanTiltVelocitySpace[0].YRange.Min,
    },
}

ptz.ContinuousMove(profile.token, Velocity=velocity)