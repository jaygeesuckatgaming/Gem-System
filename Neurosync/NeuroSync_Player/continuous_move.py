import asyncio, sys
from onvif import ONVIFCamera

try:
    import isodate
    import isodate.isodatetime
    from isodate.isoerror import ISO8601Error

    original_isodate_parse_datetime = isodate.isodatetime.parse_datetime

    def tolerant_isodate_parse_datetime(datetimestring):
        if isinstance(datetimestring, str):
            # Attempt to fix common issues like missing 'T' or just a date
            if "T" not in datetimestring:
                if " " in datetimestring: # Replace space with T
                    datetimestring = datetimestring.replace(" ", "T", 1)
                elif "-" in datetimestring and ":" not in datetimestring and len(datetimestring) == 10:
                    # Likely just a date YYYY-MM-DD, append T00:00:00Z for isodate
                    if DEBUG_MOVEMENT: # Assuming DEBUG_MOVEMENT is defined
                        print(f"[ISODATE_PATCH] Received date-only string: '{datetimestring}'. Appending 'T00:00:00Z'.")
                    datetimestring += "T00:00:00Z"
        try:
            return original_isodate_parse_datetime(datetimestring)
        except ValueError as e:
            if "not enough values to unpack" in str(e) and isinstance(datetimestring, str) and "T" not in datetimestring:
                # This specific error for this specific case might indicate other malformations
                # or it's already been modified and still fails.
                print(f"[ISODATE_PATCH] ValueError for '{datetimestring}' despite potential fix. Original error: {e}")
                # As a last resort for this specific error, if it's just a date, try adding time
                if "-" in datetimestring and ":" not in datetimestring and len(datetimestring) == 10:
                     try:
                         return original_isodate_parse_datetime(datetimestring + "T00:00:00Z")
                     except Exception as e2:
                         print(f"[ISODATE_PATCH] Still failed after force-appending T00:00:00Z: {e2}")
                         raise e # Re-raise original error
                raise e # Re-raise if not the date-only pattern
            else:
                raise # Re-raise other ValueErrors
        except ISO8601Error as e_iso:
            print(f"[ISODATE_PATCH] ISO8601Error for '{datetimestring}'. Original error: {e_iso}")
            # Potentially try more specific fixes or re-raise
            raise

    isodate.isodatetime.parse_datetime = tolerant_isodate_parse_datetime
    print("Applied tolerant monkey patch to isodate.isodatetime.parse_datetime.")
except ImportError:
    print("WARNING: 'isodate' library not found. Cannot apply timestamp parsing patch.")
except AttributeError:
    print("WARNING: Could not apply isodate patch (AttributeError). Might be an unexpected version.")

IP="192.168.1.100"   # Camera IP address
PORT="2020"          # Port
USER="jaygee"         # Username
PASS="1248aceg"        # Password


XMAX = 1
XMIN = -1
YMAX = 1
YMIN = -1
moverequest = None
ptz = None
active = False

def do_move(ptz, request):
    # Start continuous move
    global active
    if active:
        ptz.Stop({'ProfileToken': request.ProfileToken})
    active = True
    ptz.ContinuousMove(request)

def move_up(ptz, request):
    print ('move up...')
    request.Velocity.PanTilt.x = 0
    request.Velocity.PanTilt.y = YMAX
    do_move(ptz, request)

def move_down(ptz, request):
    print ('move down...')
    request.Velocity.PanTilt.x = 0
    request.Velocity.PanTilt.y = YMIN
    do_move(ptz, request)

def move_right(ptz, request):
    print ('move right...')
    request.Velocity.PanTilt.x = XMAX
    request.Velocity.PanTilt.y = 0
    do_move(ptz, request)

def move_left(ptz, request):
    print ('move left...')
    request.Velocity.PanTilt.x = XMIN
    request.Velocity.PanTilt.y = 0
    do_move(ptz, request)
    

def move_upleft(ptz, request):
    print ('move up left...')
    request.Velocity.PanTilt.x = XMIN
    request.Velocity.PanTilt.y = YMAX
    do_move(ptz, request)
    
def move_upright(ptz, request):
    print ('move up left...')
    request.Velocity.PanTilt.x = XMAX
    request.Velocity.PanTilt.y = YMAX
    do_move(ptz, request)
    
def move_downleft(ptz, request):
    print ('move down left...')
    request.Velocity.PanTilt.x = XMIN
    request.Velocity.PanTilt.y = YMIN
    do_move(ptz, request)
    
def move_downright(ptz, request):
    print ('move down left...')
    request.Velocity.PanTilt.x = XMAX
    request.Velocity.PanTilt.y = YMIN
    do_move(ptz, request)

def setup_move():
    mycam = ONVIFCamera(IP, PORT, USER, PASS)
    # Create media service object
    media = mycam.create_media_service()
    
    # Create ptz service object
    global ptz
    ptz = mycam.create_ptz_service()

    # Get target profile
    media_profile = media.GetProfiles()[0]

    # Get PTZ configuration options for getting continuous move range
    request = ptz.create_type('GetConfigurationOptions')
    request.ConfigurationToken = media_profile.PTZConfiguration.token
    ptz_configuration_options = ptz.GetConfigurationOptions(request)

    global moverequest
    moverequest = ptz.create_type('ContinuousMove')
    moverequest.ProfileToken = media_profile.token
    if moverequest.Velocity is None:
        moverequest.Velocity = ptz.GetStatus({'ProfileToken': media_profile.token}).Position


    # Get range of pan and tilt
    # NOTE: X and Y are velocity vector
    global XMAX, XMIN, YMAX, YMIN
    XMAX = ptz_configuration_options.Spaces.ContinuousPanTiltVelocitySpace[0].XRange.Max
    XMIN = ptz_configuration_options.Spaces.ContinuousPanTiltVelocitySpace[0].XRange.Min
    YMAX = ptz_configuration_options.Spaces.ContinuousPanTiltVelocitySpace[0].YRange.Max
    YMIN = ptz_configuration_options.Spaces.ContinuousPanTiltVelocitySpace[0].YRange.Min


def readin():
    """Reading from stdin and displaying menu"""
    global moverequest, ptz
    
    selection = sys.stdin.readline().strip("\n")
    lov=[ x for x in selection.split(" ") if x != ""]
    if lov:
        
        if lov[0].lower() in ["u","up"]:
            move_up(ptz,moverequest)
        elif lov[0].lower() in ["d","do","dow","down"]:
            move_down(ptz,moverequest)
        elif lov[0].lower() in ["l","le","lef","left"]:
            move_left(ptz,moverequest)
        elif lov[0].lower() in ["l","le","lef","left"]:
            move_left(ptz,moverequest)
        elif lov[0].lower() in ["r","ri","rig","righ","right"]:
            move_right(ptz,moverequest)
        elif lov[0].lower() in ["ul"]:
            move_upleft(ptz,moverequest)
        elif lov[0].lower() in ["ur"]:
            move_upright(ptz,moverequest)
        elif lov[0].lower() in ["dl"]:
            move_downleft(ptz,moverequest)
        elif lov[0].lower() in ["dr"]:
            move_downright(ptz,moverequest)
        elif lov[0].lower() in ["s","st","sto","stop"]:
            ptz.Stop({'ProfileToken': moverequest.ProfileToken})
            active = False
        else:
            print("What are you asking?\tI only know, 'up','down','left','right', 'ul' (up left), \n\t\t\t'ur' (up right), 'dl' (down left), 'dr' (down right) and 'stop'")
         
    print("")
    print("Your command: ", end='',flush=True)
       
            
if __name__ == '__main__':
    setup_move()
    loop = asyncio.get_event_loop()
    try:
        loop.add_reader(sys.stdin,readin)
        print("Use Ctrl-C to quit")
        print("Your command: ", end='',flush=True)
        loop.run_forever()
    except:
        pass
    finally:
        loop.remove_reader(sys.stdin)
        loop.close()
