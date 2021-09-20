
# version 0.1 initial version
# version 0.2 updated comments
# version 0.3 added lastTandH for Homepage
# version 0.7 thermocouple graph added +K3 data added
# version 0.8 added form for tare submission
# version 0.9 updated tare to list and reorganise dictonary
# version 0.10 added export of tare to xml file
# version 0.11 added krios 5 -krios 6
# version 0.12 added krios 7 and Glacios
# version 0.16 added krios 1-7 and Glacios
# version 0.23 redid weblink for tem / hum 
# version 0.38 redid merged all LN2 graphs in one proc 
# version 0.39 add inset graphs and arrows 
# version 0.40 updated uptime algorithm
# version 0.41 added maintenance
# version 0.44 added faciity voltage
# version 0.44 added uptime
# version 0.46 changed db access to once a minute for all data at once
# version 0.50 introduced array that buffers db data
# version 0.51 merged all graphs in one link
# version 0.52 cleaned up unused functions
# version 0.58 added EMI graphs
# version 0.60 restored uptime graphs
# version 0.63 added pH krios 5
# version 0.64 redesign uptime code and webpage
# version 0.72 redesign webpage. auto refresh uptime. emi integrated
# version 0.73 added up / down time editor
# version 0.78 added pH for Krios 7. Table is now complete. Algorithm can remove exept.
# version 0.81 removed EMI from email. Too many empty string errors
# version 0.82 added login form and classes


#from app import app

import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import sqlite3, threading
import io, os.path, time

from queue import *
from sqlite3 import Error
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from flask import Flask, render_template, send_file, make_response, request, flash, redirect
from matplotlib.ticker import MultipleLocator, FormatStrFormatter, AutoMinorLocator

from forms import LoginForm


###

class myThread (threading.Thread):
   def __init__(self, action):
      threading.Thread.__init__(self)
      self.action = action
      
   def run(self):
      self.action()
###


app = Flask(__name__)
app.config['SECRET_KEY'] = 'you-will-never-guess'

dbdir='../FacilityData.db'

tare_file='../tare.xml'
kg2lb=2.20462
numsamples = 3000
numMaxSamples=5002

all_response   = [0]
all_tares      = []
all_times, all_temps, all_hums, all_ln2s = [[]], [[]], [[]], [[]]



def send_email(update):
    
    # configure  mail
    smtp_server = "outlook.office365.com"
    
    #sender_email = "kriosd3486@nysbc.org"
    sender_email = "raspberrypi-alerts@nysbc.org"
    receiver_email = ["malink@nysbc.org"]

    #input("Type your password and press enter: ")
    password = ""


    # Create a secure SSL context
    context = ssl.create_default_context()

    text = """
      This email update is html only
    """
    html = update

    message = MIMEMultipart(
        "alternative", None, [MIMEText(text), MIMEText(html,'html')])

    message['Subject'] ="Daily update " # +time.strftime("%m/%d/%y", time.localtime(time.time() ))    
    #Try to log in to server and send email
    try:
        server = smtplib.SMTP(smtp_server,port)
        server.ehlo() # Can be omitted
        server.starttls(context=context) # Secure the connection
        server.ehlo() # Can be omitted
        server.login(sender_email, password)
        # Send email here
        server.sendmail(sender_email, receiver_email, message.as_string())

    except Exception as e:
        # Print any error messages to stdout
        print(e)
    finally:
        server.quit()

########


def oldest(microscopefolder):
   files = os.listdir(microscopefolder)                # all files in full directory
   files = [f for f in files if f[0:6] == 'Health']

   if len(files)>0:                          # one update needs 3 logs available
      paths = [os.path.join(microscopefolder, basename) for basename in files]
      return min(paths, key=os.path.getctime)   # return oldest log file
   else:
      return ''             

def csv_reader(file_name):
    for row in open(file_name, "r"):
       yield row

def look4log(nr):
   updated = False
   path = os.getcwd() + '/uptime/' 
   pathpub = '/home/pi/Public'
   
   foldername = systemserialnr( 'k'+str(nr) )            # lookup system folder name
   microscopefolder = os.path.join(pathpub, foldername)  # lookup full directory
   file = oldest(microscopefolder) # oldest file moved first and gets overwritten
      
   # get three latest files
   while len(file):
   #for c in range(3):
      updated = True
      os.chown(file, 1000, 1000)      # change ownership and group to pi (UID = 1000)

      csv_gen = csv_reader(file)
      for r in range(9):              # get rid of 7 toplines, return 8th line
         test = (csv_gen.__next__())
      if ( 'Holder Temperature' in test):
         os.rename(file, 'uptime/k'+str(nr)+'Cryo.csv')
      elif ('Nominal Magnification' in test ):
         os.rename(file, 'uptime/k'+str(nr)+'ColMag.csv')
      else:
         os.rename(file, 'uptime/k'+str(nr)+'Col.csv')

      file = oldest(microscopefolder) # oldest file moved first and gets overwritten
      time.sleep(3)

   return (updated)

         

def systemserialnr(argument):
    switcher = {
        'k1': '3486_TitanKriosG2',
        'k2': '3570_TitanKriosG2',
        'k3': '3663_TitanKriosG2',
        'k4': '3848_TitanKriosG3i(3.1)',
        'k5': '3846_TitanKriosG3i(3.1)',
        'k6': '3855_TitanKriosG3i(3.1)',
        'k7': '3889_KriosG4',
        'k8': '9953149_Glacios'
    }
    return switcher.get(argument, '3486_TitanKriosG2')

def system_dnr(argument):
    switcher = {
        'k1': '3486',
        'k2': '3570',
        'k3': '3663',
        'k4': '3848',
        'k5': '3846',
        'k6': '3855',
        'k7': '3889',
        'k8': '9953149'
    }
    return switcher.get(argument, '3486')
   



##########################################

            
def init_sensordata(system, numsamples):
    dates, temps, hums, ln2s = [], [], [], []

    succes = False
    while not (succes):
        try:
            conn = sqlite3.connect(dbdir)
            curs = conn.cursor()
            curs.execute("SELECT * FROM Sensor_data WHERE system = (?) ORDER BY timestamp DESC LIMIT (?)", (system, numsamples))
            data = curs.fetchall()
            succes = True

        except Error as e:
            print('Database connection error: ' + str(e))
            time.sleep(1)
            succes = False
   
    conn.close()

    for row in reversed(data):
        dates.append(row[0])
        temps.append(row[3])
        hums.append(row[4])
        ln2s.append(row[5])
    return dates, temps, hums, ln2s

            
def init_pHdata(system, numsamples):
    dates, temps, pHs = [], [], []

    succes = False
    while not (succes):
        try:
            conn = sqlite3.connect(dbdir)
            curs = conn.cursor()
            curs.execute("SELECT * FROM Sensor_data WHERE system = (?) ORDER BY timestamp DESC LIMIT (?)", (system, numsamples*10))
            data = curs.fetchall()
            
            succes = True

        except Error as e:
            print('Database connection error: ' + str(e))
            time.sleep(1)
            succes = False
   
    conn.close()

    counter = 0
    for row in reversed(data):
      if not(counter % 10):   #make time scale 10 larger by only selecting every 10th entry. At some point aver needed
         dates.append(row[0])
         temps.append(row[3])
         pHs.append(row[4])
         #ln2s.append(row[5])
      counter +=1

    return dates, temps, pHs


def new_sensordata(system, start):
    dates, temps, hums, ln2s = [], [], [], []  

    succes = False
    while not (succes):
        try:
            conn = sqlite3.connect(dbdir)
            curs = conn.cursor()
            curs.execute("SELECT * FROM Sensor_data WHERE timestamp > (?) AND system = (?) ORDER BY timestamp DESC", (start, system))
            data = curs.fetchall()
            succes = True

        except Error as e:
            print('Database connection error: ' + str(e))
            time.sleep(1)
            succes = False
    conn.close()

    for row in reversed(data):
        dates.append(row[0])
        temps.append(row[3])
        hums.append(row[4])
        ln2s.append(row[5])      
    return dates, temps, hums, ln2s

######################################

def getSensorData(index, numsamples):
   
    times = all_times[index][-int(numsamples):]
    temps = all_temps[index][-int(numsamples):]
    hums =  all_hums[index][-int(numsamples):]
    ln2s =  all_ln2s[index][-int(numsamples):]
    
    return times, temps, hums, ln2s


@app.route('/')
def tare():

    global all_tares
    numsamples = 3000
    day   = time.localtime(time.time()).tm_mday
    
    del(all_tares[:])
    with open (tare_file,"r") as fo:
        str_tares=fo.read()

    listed_tares=str_tares.split("</k")
    for i, sep_tare in enumerate (listed_tares):
        if(sep_tare[-3:].isnumeric()):
            all_tares.append(int(sep_tare[-3:]))


    times, temp, hum, ln2s = getSensorData(10, 1) # latest tem / hum from rasp 1
    timestr = time.strftime('%X ',time.localtime(int(times[0])))
    templateData = {
                    'time'	: timestr,
                    'temp'	: temp,
                    'hum'	: hum,
                    'numsamples': numsamples
                    }
    for k in range(1, 9):

        templateData['tarek'+str(k)] = all_tares[k]
        templateData['nettk'+str(k)] = all_ln2s[k][-1]-all_tares[k]
        templateData['downk'+str(k)] = down_krios[k][day]
       

    return render_template('index.html', **templateData)

@app.route('/', methods=['POST'])
def tare_form_post():

    global numsamples, all_tares

    day   = time.localtime(time.time()).tm_mday
    numsamples = int (request.form['numsamples'])

    numMaxSamples = 5001
    if (numsamples > numMaxSamples):
        numsamples = (numMaxSamples-1)

    # get tares    
    for k in range(1, 9):
        all_tares[k]= int(request.form['tarek'+str(k)])


    # save updated tares from website to tare.xml
    with open (tare_file, "w") as fo:
        for i, tare in enumerate(all_tares):
            tare_str='<krios'+str(i)+'>'+str(tare)+'</krios'+str(i)+'>\n'
            fo.write(tare_str)

    times, temp, hum, ln2s = getSensorData(10, 1) # latest tem / hum from rasp 1
    timestr = time.strftime('%X ',time.localtime(int(times[0])))

    templateData = {
                    'time'          : timestr,
                    'temp'          : temp,
                    'hum'           : hum,
                    'numsamples'    : numsamples
                    }
    for k in range(1, 9):

        templateData['tarek'+str(k)] = all_tares[k]
        templateData['nettk'+str(k)] = all_ln2s[k][-1]-all_tares[k]
        templateData['downk'+str(k)] = down_krios[k][day]
	
    return render_template('index.html', **templateData)


@app.route('/live')
def live():        

    numsamples = 3000
    day    = time.localtime(time.time()).tm_mday
    scope = str((time.localtime(time.time()).tm_sec % 8) + 1)  
     
    times, temp, hum, ln2s = getSensorData(10, 1) # latest tem / hum from rasp 1
    timestr = time.strftime('%X ',time.localtime(int(times[0])))


    def update_link(argument):
        switcher = {
            1   : ( 'y', 'jg1', 'graph/ln2k1', '/emi/emik1', '/graph/tempk1', '/graph/humk1', '/graph/pHk21', '', ''),
            2   : ( 'y', 'jg2', 'graph/ln2k2', '/emi/emik2', '/graph/tempk2', '/graph/humk2', '/graph/pHk22', '', ''),
            3   : ( 'y', 'jg3', 'graph/ln2k3', '/emi/emik3', '/graph/tempk3', '/graph/humk3', '/graph/pHk23', '', ''),
            4   : ( 'y', 'jg4', 'graph/ln2k4', '/emi/emik4', '/graph/tempk4', '/graph/humk4', '/graph/pHk24', '', ''),
            5   : ( 'y', 'jg5', 'graph/ln2k5', '/emi/emik5', '/graph/tempk5', '/graph/humk5', '/graph/pHk25', '', ''),
            6   : ( 'y', 'jg6', 'graph/ln2k6', '/emi/emik6', '/graph/tempk6', '/graph/humk6', '/graph/pHk26', '', ''),
            7   : ( 'y', 'jg7', 'graph/ln2k7', '/emi/emik7', '/graph/tempk7', '/graph/humk7', '/graph/pHk27', '', ''),
            8   : ( 'y', 'jg8', 'graph/ln2k8', '/emi/emik6', '/graph/tempk8', '/graph/humk8', '/graph/pHk28', '', ''),

            9   : ( 'n', '/plot/bars/k1', '/plot/pie/k1', '/plot/bars/k2', '/plot/pie/k2', '/plot/bars/k3', '/plot/pie/k3', '/plot/bars/k4', '/plot/pie/k4'),
            10  : ( 'n', '/plot/bars/k5', '/plot/pie/k5', '/plot/bars/k6', '/plot/pie/k6', '/plot/bars/k7', '/plot/pie/k7', '/plot/bars/k8', '/plot/pie/k8')
            }
        arg = int((time.localtime(time.time()).tm_min % 10) + 1)


        # lookup all links
        return switcher.get(arg, 1)
    
    link1, link2, link3,link4, link5, link6, link7, link8, link9 = update_link(1)
    
    templateData = {
                    'time'	: timestr,
                    'temp'	: temp,
                    'hum'	: hum,
                    'scope'     : scope,
                    'link1'     : link1,
                    'link2'     : link2,
                    'link3'     : link3,
                    'link4'     : link4,
                    'link5'     : link5,
                    'link6'     : link6,
                    'link7'     : link7,
                    'link8'     : link8,
                    'link9'     : link9,                    
                    'numsamples': numsamples
                    }
    for k in range(1, 9):

        templateData['nettk'+str(k)] = all_ln2s[k][-1]-all_tares[k]
        templateData['downk'+str(k)] = down_krios[k][day]

    return  render_template('live.html', **templateData)



@app.route('/login', methods=['GET', 'POST'])
def login():

    user = {'username': 'Mike'}
    posts = [
        {
            'author': {'username': 'John'},
            'body': 'New York never sleeps!'
        },
        {
            'author': {'username': 'Susan'},
            'body': 'Hundred percent uptime, zero stress!'
        }
    ]
   
    form = LoginForm()
    #form.username.data = 'Michael is here'
    if form.validate_on_submit():
        flash('Login requested for user {}, remember_me={}'.format(
            form.username.data, form.remember_me.data))
        return redirect('/uptime')
    return render_template('login.html', title='Sign In', form=form, user=user, posts=posts)    


from forms import PostForm

@app.route('/calls/<req>', methods=['GET'])
@app.route('/calls/<req>/', methods=['GET'])

def calls_get(req):

   global all_status, all_steps

   day   = time.localtime(time.time()).tm_mday
   
   system = int(req)
   microscope = lookup_microscope('k'+req)

   path    = os.path.join(os.getcwd(), 'Appdata/')

   call = all_status[system][day]
   step = all_steps[system][day]     
   form = PostForm()
   form.call.data = call
   form.step.data = step

   

   update = {'system': microscope,
             'down'  : True * down_krios[system][day]
            }
 
   return render_template("calls.html", title='calls Page', form=form, update = update)


@app.route('/calls/<req>', methods=['POST'])
@app.route('/calls/<req>/', methods=['POST'])

def calls(req):

   global all_status, all_steps
   # all_status is current status on overview page, all_steps: all next steps

   day   = time.localtime(time.time()).tm_mday
   month  = time.localtime(time.time()).tm_mon
   
   system = int(req)
   microscope = lookup_microscope('k'+req)

   path    = os.path.join(os.getcwd(), 'Appdata/')

   call = all_status[system][day]
   step = all_steps[system][day]     
   form = PostForm()
   
   if form.validate_on_submit():
      call = form.call.data
      if len(call)>0:
          for d in range(day,32):
              # make sure all status data is copied to next days.
              all_status[system][d] = call #.replace('\n',' ')
      step = form.step.data
      if len(step)>0:
          for d in range(day,32):
              # make sure all steps data is copied to next days.              
              all_steps[system][d] = step #.replace('\n',' ')
         
      data2file(all_status, path + lookup_month(month) +'_calls_krios.csv')
      data2file(all_steps, path + lookup_month(month) +'_steps_krios.csv')      
         
      return redirect('/uptime')

   update = {'system': microscope,
             'down'  : True * down_krios[system][day]
            }
 
   return render_template("calls.html", title='calls Page', form=form, update = update)


   

@app.route('/toggle/<system>/<status>/')
def toggle(system, status):
    # this route allows toggling up / down status of systems
    # all routes lead to /toggle template
    # the <system> variable decides which system to toggle
    # the <status> variable decided if is will go up or down
   
   day   = time.localtime(time.time()).tm_mday

   microscope_name = lookup_microscope(system)
   microscope_nr  = int(system[-1])
   month          = month_krios[microscope_nr]

##   if (status == 'down'):
##      #  e.g. 1 in case the system is down on a day
##      for d in range(day, 32):
##          down_krios[microscope_nr][d] = 1
##   else:
##      for d in range(day, 32):
##          down_krios[microscope_nr][d] = 0

   timestr = time.strftime('%X ',time.localtime(int(time.time())))
   templateData = {
                 'time'	: timestr
                 }
   for k in range(1, 9):
     templateData['downk'+str(k)] = down_krios[k][day]

   data2file(down_krios, lookup_month(month) +'_down_krios.csv')

   return render_template('toggle.html', **templateData)


@app.route('/graph/<req>')
#htempk1
def plot_sensor(req):
    times, ys, title = lookup_graph(req)  #retrieve sensor data

    times = times[-numsamples:]
    ys = ys[-numsamples:]

    newnumsamples = len(ys)
    xs=range(len(ys))
    
    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)
        
    axis.set_title(title) # + " - now: %d\n " % (ys[(len(ys)-1)])) #tare: %d kg --- %d lb." % (all_tares[1]/2.20, all_tares[1]))

    axis.grid(True)
    N=newnumsamples/6
    axis.xaxis.set_major_locator(MultipleLocator(N))
    axis.tick_params(width=5)

    for tick in axis.get_xticklabels():
        tick.set_rotation(15)

    time1 = time.strftime( '%b %d - %H:%M', time.localtime(times[0]) )
    time2 = time.strftime( '%H:%M', time.localtime(times[int(0.167*len(times))] ))
    time3 = time.strftime( '%H:%M', time.localtime(times[int(0.333*len(times))] ))
    time4 = time.strftime( '%b %d - %H:%M', time.localtime(times[int(0.5*len(times))] ))
    time5 = time.strftime( '%H:%M', time.localtime(times[int(0.667*len(times))] ))
    time6 = time.strftime( '%H:%M', time.localtime(times[int(0.833*len(times))] ))
    time7 = time.strftime( '%b %d - %H:%M', time.localtime(times[len(times)-1] ))

    axis.set_xticklabels([' ', time1, time2, time3, time4, time5, time6, time7 ])


    axis.plot(xs, ys)
    
    canvas = FigureCanvas(fig)
    output = io.BytesIO()
    canvas.print_png(output)
    response = make_response(output.getvalue())
    response.mimetype = 'image/png'
    #Fall_response=[]
    #all_response.append(response)
    return response

@app.route('/emi/')
@app.route('/emi')
def emi():

    return render_template('emi.html')

@app.route('/emi/<req>')
#emi/emik1
def plot_threecurves(req):
    times, curve1, title = lookup_graph(req+'x')  #retrieve sensor data
    times, curve2, title2 = lookup_graph(req+'y')  #retrieve sensor data
    times, curve3, title = lookup_graph(req+'z')  #retrieve sensor data

    times = times[-numsamples:]
    curve1 = curve1[-numsamples:]
    curve2 = curve2[-numsamples:]
    curve3 = curve3[-numsamples:]

    newnumsamples = len(times)
    xs=range(len(times))
    
    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)
    axis2 = fig.add_subplot(1, 1, 1)
    axis3 = fig.add_subplot(1, 1, 1)

    fig.legend()

    axis.set_title(title ) # + " - now: %d\n " % (ys[(len(ys)-1)])) #tare: %d kg --- %d lb." % (all_tares[1]/2.20, all_tares[1]))
    #axis.set_xlabel("Samples")
    axis.grid(True)
    N=newnumsamples/6
    axis.xaxis.set_major_locator(MultipleLocator(N))
    axis.tick_params(width=5)

    for tick in axis.get_xticklabels():
        tick.set_rotation(15)

    time1 = time.strftime( '%b %d - %H:%M', time.localtime(times[0]) )
    time2 = time.strftime( '%H:%M', time.localtime(times[int(0.167*len(times))] ))
    time3 = time.strftime( '%H:%M', time.localtime(times[int(0.333*len(times))] ))
    time4 = time.strftime( '%b %d - %H:%M', time.localtime(times[int(0.5*len(times))] ))
    time5 = time.strftime( '%H:%M', time.localtime(times[int(0.667*len(times))] ))
    time6 = time.strftime( '%H:%M', time.localtime(times[int(0.833*len(times))] ))
    time7 = time.strftime( '%b %d - %H:%M', time.localtime(times[len(times)-1] ))

    axis.set_xticklabels([' ', time1, time2, time3, time4, time5, time6, time7 ])

    axis.plot(xs, curve1)
    axis2.plot(xs, curve2)
    axis3.plot(xs, curve3)

    canvas = FigureCanvas(fig)
    output = io.BytesIO()
    canvas.print_png(output)
    response = make_response(output.getvalue())
    response.mimetype = 'image/png'
    #all_response=[]
    #all_response.append(response)
    return response

def system_status(timestr):

   print(" === Daily system status update ===")
   global all_status, all_steps
   updatestart = time.time()
   day   = time.localtime(time.time()).tm_mday 
   
   # part for slack 
   width = 12 #    table cel width

   slacktext= time.strftime( '\n Update %D - %I:%M %p \n', time.localtime(updatestart ))
                 
   line = '\n'
   line += ' '.ljust(width,'=')
   line += ' '.ljust(width,'=')
   line += ' '.ljust(width,'=')
   line += '\n'

   slacktext += line

   width += 7  # spaces force more cel width
   slacktext += ' System'.ljust(width,' ')
   slacktext += ' Weight (lb.)'.ljust(width,' ')
   slacktext += ' days'.ljust(width,' ')
   slacktext += line
   slacktext += '\n'

   width += 2 # numbers have lost of space so increase

   ##  email update html
   html = """<html><head><style>
        table {font-family: arial, sans-serif; border-collapse: collapse; width: 100%;}
        td, th {border: 1px solid #dddddd; text-align: left; padding: 8px;}
        </style></head><body>
        <h2>SEMCi daily system status </h2>"""
   html+= time.strftime( '<h4>Update %D - %I:%M %p </h4>', time.localtime(updatestart ))
   html+="""<table><thead><tr>
     <th>Equipment</th>
     <th>Status</th>
     <th>days</th>
     <th> details </th>
     </tr></thead><tbody>"""

   #numSamples = 24*60      # 24 hour moving average for tem - hum
   warnings=[]
   warnings.append("\n\n")

   for i in range(1,9):    # Krios 1 - 7 , Krios 8 = Glacios
      down = down_krios[i][day]
      if down:
          days = down_krios[i][1:day+1].count(1) # number of down days this month
      else:
          days = down_krios[i][1:day+1].count(0) # number of up days this month
          
          
      #start of new table row
      html += '<tr>'
      
      # Column system name
      if i == 8:
         system = 'Glacios'
      else:
         system = 'Krios ' + str(i)
      html+= '<td>' + system + '</td>'
      slacktext += (' '+system).ljust(width,' ')


     
      # Column status up/down
      if down:          
         html+= '<td style="background-color:#FFECD9" > down </td>'
         slacktext += ' down'.ljust(width,' ')
      else:
         html+= '<td style="background-color:#E7FFD9" > up </td>' #CCF5B5
         #html+= """<td> up </td>"""
         slacktext += ' up'.ljust(width,' ')

      # Column days
      html+= '<td>' + str(days) + '</td>'
      slacktext += str(days).ljust(width,' ')

      # Column details
      width = 12
      html+= '<td>' + all_status[i][day] + '</td>'
      slacktext += all_status[i][day].ljust(width,' ')
  
      html += '</tr>'
   html+= '</tbody></table>'
   
   html += 'Note: days indicate current number of days the system has been up/down  this month <br>'

   html += '<br><br><h3>Overview: </h3>'

   #issues
   # all Krios 
   for i in range(1,9):
      html += '<p>'
      
      html += '<h3>'
      if (i==8):
         system = 'Glacios'
      else:
         system = 'Krios ' + str(i)
    
      html += system + ': <br>'
      html += '</h3>'

      html += 'Status: ' + all_status[i][day] + '<br>'
      html += 'Next steps:  '+ all_steps[i][day] + '<br>'

      html += '</p>'  
   
      

   return (html)
   
@app.route('/uptime')
@app.route('/uptime/')
def uptime():
   global all_status, all_steps
   updates = []
    
   timestr = time.strftime('%X ',time.localtime(int(time.time())))
   day   = time.localtime(time.time()).tm_mday
   
   # all Krios 
   for i in range(1,8):
      updates.append(
            {
            'system': 'Krios '+ str(i),
            'down': True * down_krios[i][day],
            'status': all_status[i][day],
            'step': all_steps[i][day],
            'link': '/calls/'+str(i)
            }
         )
   # glacios
   updates.append(
         {
         'system': 'Glacios',
         'down': True * down_krios[8][day],
         'status': all_status[8][day],
         'step': all_steps[8][day],
         'link': '/calls/'+str(8)         
         }
      )
          
   templateData = {'time'	: timestr }
  
   message = system_status(timestr)
   send_email(message)        
   return render_template('uptime.html', **templateData, updates = updates)
     
   
@app.route('/uptime/<month>')
def uptime_hist(month):

    pathpub = '/home/pi/Public'


    if month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August']:
       path = 'uptime_' + month + '.html'
    else:
       path = 'uptime.html'
 
    timestr = time.strftime('%X ',time.localtime(int(time.time())))
    templateData = {
                     'month'        : month,
                     'time'         : timestr
                    }


    return render_template(path, **templateData)
   
####################################################################

@app.route('/plot/pie/<req>')
def plot_pie(req):

    microscope_name = lookup_microscope(req)
    microscope_nr = int(req[-1])

    down =              down_krios[microscope_nr]
    sum_down=           sum(down)*86400

    for day in range(1, 32):
        if down[day] == 1:
            cryo_krios[microscope_nr][day] = closed_krios[microscope_nr][day] = mag_krios[microscope_nr][day] = open_krios[microscope_nr][day] = 1


    sum_cryo=           sum(cryo_krios[microscope_nr])
    sum_closed=         sum(closed_krios[microscope_nr])  
    sum_standby =       sum_closed - sum_cryo
               
    sum_open=           sum(open_krios[microscope_nr])    
    sum_mag =           sum(mag_krios[microscope_nr])    
    sum_engineering=    sum_open - sum_mag + 172800

    month_name = lookup_month( month_krios[microscope_nr] )
    
    # Pie chart, where the slices will be ordered and plotted counter-clockwise:
    labels = 'Cryocycle time', 'Standby time', 'Collecting data', 'Maintenance time', 'Engineering time'
    sizes = [sum_cryo, sum_standby, sum_mag, sum_down, sum_engineering]
    explode = (0.1, 0.1, 0.1, 0.1, 0.1)  # explode all slices by 10% 

    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)
    axis.set_title(microscope_name+'\nUptime graph '+ month_name +' 2021')

    colors = ['orange', 'grey', 'limeGreen', 'brown', 'cyan', 'lime'] #

    axis.pie(sizes, explode=explode, labels=labels, autopct='%1.1f%%',
            shadow=True, startangle=180)
    axis.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    
    canvas = FigureCanvas(fig)

    # save pie picture each system each month in archive
    path    = os.path.join(os.getcwd(), 'static', 'images', month_name)
    if not os.path.exists(path):
       os.mkdir(path)
    fig.savefig(path + '/k'+ str(microscope_nr) + 'pie.png')

    output = io.BytesIO()
    canvas.print_png(output)
    response = make_response(output.getvalue())
    response.mimetype = 'image/png'

           
    return response

####################################################################


@app.route('/plot/bars/<req>')
def plot_bars(req):

    microscope_name =   lookup_microscope(req)
    microscope_nr =     int(req[-1])
    month_name =        lookup_month( month_krios[microscope_nr] )

    sum_cryo =          cryo_krios[microscope_nr]
    cryo_perc =         [y/864 for y in sum_cryo]
    num_days =          len(sum_cryo)

    sum_closed =        closed_krios[microscope_nr]
    closed_perc=        [y/864 for y in sum_closed]
    
    standby_perc =   [ ( closed_perc[t] - cryo_perc[t] ) for t in range( num_days) ]

    sum_open =          open_krios[microscope_nr]
    open_perc=          [y/864 for y in sum_open]
    
    sum_mag =           mag_krios[microscope_nr]
    mag_perc=           [y/864 for y in sum_mag]

    engineering_perc =  [ ( open_perc[t] - mag_perc[t] ) for t in range( num_days) ]
    engineering_bottom= [ (closed_perc[t] + mag_perc[t]) for t in range( num_days) ]

    sum_down =          down_krios[microscope_nr]
    down_perc=          [y/864 for y in sum_down]

    for day in range(1, 32):
        if sum_down[day] == 1:
            down_perc[day] = 100
            cryo_perc[day] = standby_perc[day] = mag_perc[day] = engineering_perc[day] = 0
        else:
            down_perc[day] = 0


    
    labels = range( num_days ) # dates
    width = 0.5       # the width of the bars: can also be len(x) sequence

    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)
    axis.bar(labels, cryo_perc, width, label='Cryocycle Time')
    axis.bar(labels, standby_perc, width, bottom=cryo_perc, label='Standby Time')
    
    axis.bar(labels, mag_perc, width, bottom=closed_perc, label='Collecting data')
    axis.bar(labels, down_perc, width, label='Maintenance Time')
    axis.bar(labels, engineering_perc, width, bottom=engineering_bottom, label='Engineering time')


    axis.set_ylabel('Percentage')
    axis.legend(loc='center left')

    axis.set_title(microscope_name + "\nDaily breakdown "+ month_name)

    axis.grid(True)

    if microscope_nr == 7:
        axis.annotate('N400558: Autoloader\n un-initialize',
                      xy=(1, 5), xycoords='data', xytext=(5, 10), textcoords='data',
                      bbox=dict(boxstyle="round", fc="0.8"),
                      arrowprops=dict(arrowstyle="->",connectionstyle="angle,angleA=0,angleB=90,rad=10"))

    if microscope_nr == 8:
        axis.annotate('N400993 \n Gun align',
                      xy=(8, 5), xycoords='data', xytext=(12, 10), textcoords='data',
                      bbox=dict(boxstyle="round", fc="0.8"),
                      arrowprops=dict(arrowstyle="->",connectionstyle="angle,angleA=0,angleB=90,rad=10"))


    canvas = FigureCanvas(fig)

    # save bars picture each system each month in archive
    path    = os.path.join(os.getcwd(), 'static', 'images', month_name)
    if not os.path.exists(path):
       os.mkdir(path)
    fig.savefig(path + '/k'+ str(microscope_nr) + 'bars.png')
    
    output = io.BytesIO()
    canvas.print_png(output)
    response = make_response(output.getvalue())
    response.mimetype = 'image/png'
    return response


##########################################################################################



@app.route('/plot/thruput/<req>')
def plot_thruput(req):

    microscope_name =   lookup_microscope(req)
    microscope_nr =     int(req[-1])
    month_name =        lookup_month( month_krios[microscope_nr] )

    exps =              [ e*10 for e in exps_krios[microscope_nr]]
    num_days =          len(exps)

    labels = range( num_days ) # dates
    width = 0.75       # the width of the bars: can also be len(x) sequence

    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)
    axis.bar(labels, exps, width, label='throughput in images')

    axis.set_ylabel('number of images')
    axis.legend(loc='center left')

    axis.set_title(microscope_name + "\nDaily breakdown "+ month_name)
    #axis.set_xlabel("Samples")
    axis.grid(True)


#################################################################################
        



    canvas = FigureCanvas(fig)


    
    output = io.BytesIO()
    canvas.print_png(output)
    response = make_response(output.getvalue())
    response.mimetype = 'image/png'
    return response


def uptime_stats(req):

    opentimes   =  []   # arrays that hold entries for each day of month
    closedtimes =  []
    cryotimes   =  []
    magtimes    =  []
    numexphighs =  []
    numexplows  =  []

    dates =  []         # 1D array holding all dates
    sheet =  []         # 2D array vert: time, hor rows: events col open data (for 1 Krios)
    
    opensec    = [0]*32    # 1D array for open times, day 0 has 0 seconds
    closedsec  = [0]*32    # 1D array for closed times, day 0 has 0 seconds
    cryo       = [0]*32    # 1D array for cryo hours per day, day 0 has 0 seconds
    mag        = [0]*32    # 1D array for mag times, day 0 has 0 seconds
    exps       = [0]*32    # 1D array for number of exposure, day 0 has 0 exposures


    # prepare open / close data from file
    fname= 'uptime/'+req+'Col.csv'
    content = look4data(fname)

    t0=time.time()

    # get rid of all month till startmonth, this is first month with at least two days
    enddate    =  int(content[-1][4:6])     # finding most recent month with sufficient data    
    activemonth = int(content[-1][1:3])     # This is the last month available in the content
        
    if enddate == 1:
    #if enddate < 3:
       
       if activemonth  == 1:
          activemonth = 12
       else:
          activemonth -=1
       enddate = 31

    month =  int(content[1][1:3]) # skip first entry to keep init value out of sum
    while month != activemonth:    # find month, day 1
      del content[0]
      month =  int(content[1][1:3])     
    
    #built the work sheet
    for items in content:
        row=items.split('"')                    # the split creates a 1D array
        del row[0], row[1:2], row[2:3], row[3]  # keep only date and open/close info
        dates.append( int(row[0][3:5]))         # array of integers with date
        sheet.append(row)                       # 2d array with date/time/open/close

##       

    # built array with valve open / close times 
    for i in range(1, len(sheet)-1):   # note first and last entry are not added, just boundary
        prerow=sheet[i-1]
        row=sheet[i]
        postrow=sheet[i+1]
       
        opentime=0
        if row[2] == 'Open (2)':
            if row[0] == postrow[0]:   #if no date change then post-curr
                opentime = ( time2sec(postrow[1]) - time2sec(row[1]) )
            else:                      # if date change then count seconds till end of day
                opentime = (86400- time2sec(row[1]) )

        #H50*(A51<>A50)*B51*24*60
        if (prerow[2] == 'Open (2)') and (row[0] != prerow[0]): #chk for date change, add leftover 
            opentime += time2sec(row[1]) #added leftover secs previous day 
        opentimes.append(opentime)

        # add this section to fill till finish of last day
        if row[0] == postrow[0]:   #if no date change
            if postrow[2] == 'Open (2)':
                opentime += (86400- time2sec(postrow[1]) )



    dates.pop(0)
    dates.pop(-1)
    
    day = dates[0]    # day is first day that will be summed 
    opentime = 0      # opentimes.pop(0)
    closedtime = 0    # closedtimes.pop(0)
    
    # merge entries of one day into one number          
    for date in dates:
        #print('\nmerge entries of one day into one number : ', date, day)
        if  date == day:
            opentime +=     opentimes.pop(0)
            #closedtime +=   closedtimes.pop(0)

        if  date > day:  # start next day
           
            opensec[day]  = opentime 
            #closedsec[day] = closedtime
            closedsec[day] = 86400 - opentime

            opentime =     opentimes.pop(0)
            #closedtime =   closedtimes.pop(0)
            day = date

    opensec[day]  = opentime 

    closedsec[day] = 86400 - opentime
    
    sumsec = [ opensec[i] + closedsec[i] for i in range (len(opensec)) ]


#################################################################

    # prepare cryo data from file
    fname= 'uptime/'+ req+'Cryo.csv'
    content = look4data(fname)

    # get rid of all month till startmonth, offset is extra day to add at start

    month = int(content[1][1:3]) # skip first entry to keep init value out of sum
    while month != activemonth:    # find month, day 1
      del content[0]
      month =  int(content[1][1:3])

    
    #built the work sheet
    dates =   []                          # clear dates arrays. cyro has different entries   
    sheet =   []                          # clear sheet arrays. cyro has different entries   

    for items in content:
        row=items.split('"')                    # the split creates a 1D array
        del row[0], row[1:2], row[2:3], row[3]  # keep only date and cryo info
        dates.append( int(row[0][3:5]))         # array of integers with date
        sheet.append(row)                      # 2d array with date/time/cryo


    # built array with cryo times
    for i in range(1, len(sheet)-1):   # note first and last entry are needed for algorithm
        prerow=sheet[i-1]
        row=sheet[i]
        postrow=sheet[i+1]
        
        temperature = float(row[2])
        cryotime=0
        if temperature >200 :   # start of cryo cycle
            if row[0] == postrow[0]:   #if no date change then post-curr
                cryotime = ( time2sec(postrow[1]) - time2sec(row[1]) )

            else:                      # if date change then count till end of month
                cryotime = (86400- time2sec(row[1]) ) # day changed

        #H50*(A51<>A50)*B51*24*60
        if float(prerow[2]) > 200 and row[0] != prerow[0]: #chk for date change, add leftover 
            cryotime += time2sec(row[1]) 
        cryotimes.append(cryotime)   #  paired with dates
        
    #  add this section to fill till finish of last day
    if row[0] == postrow[0]:   #if no date change
        if float(postrow[2]) > 200:
            cryotimes[-1] += (86400- time2sec(postrow[1]) )
 
    # At this point we have array dates, cryotimes
    # len of array dates is 2 items bigger because we need start and end value to calc time diff
    # next is to sum all secs from cryotimes data from one day into one number per day

    #cryo.append(0)
    dates.pop(0)
    dates.pop(-1)
    
    day = dates[0]    # day is first day that will be summed 
    cryotime = 0      # opentimes.pop(0)
    
    # merge entries of one day into one number          
    for date in dates:

        if date > enddate:
            cryo[date] = 0
        else:      
            if  date == day:
                cryotime +=     cryotimes.pop(0)

            if  date > day:  # start next day
                #cryo[day] = min(cryotime, closedsec[day]) # column has to be closed during cryo
                cryo[day] = cryotime # column has to be closed during cryo

                cryotime = cryotimes.pop(0)
                day = date
            
    # finally day 31st has to be added
    if date > enddate:
        cryo[day] = 0 
    else:
        cryo[day] = cryotime # column has to be closed during cryo
        #cryo[day] = min(cryotime, closedsec[day]) # column has to be closed during cryo


##################################################################

    fname= 'uptime/'+req+'ColMag.csv'
    content = look4data(fname)
##    

    
    month = int(content[1][1:3]) # skip first entry to keep init value out of sum
    while month != activemonth:    # find month, day 1
      del content[0]
      month =  int(content[1][1:3])
      
    #built the work sheet
    dates = []             # reset dates array
    sheet = []             # reset sheet for new data
    ColOpen = False        # only rec Mag if Col valves are open
    magnify = '80742.017'  # init valid mag
    #magnify = '33080'

    
    for items in content:
        # built row: date, time, mag, open/closed
        row=items.replace('"','').split(',')    # the split creates a 1D array
     
        # add true to row[3] if column valves open (mag counts)
        if row[3] != '\n':                      # meaning row[3] contains open/close info
            ColOpen = (row[3] == 'Open (2)\n')
            row[2] = magnify                    
            row[3] = ColOpen                    # adding open/close info to Mag rows
          
        else:
            row[3] = ColOpen
            magnify = row[2]                    # adding mag info to row with open/close

        dates.append( int(row[0][3:5]))         # array of integers with date
        sheet.append(row)                       # 2d array with row of date/time/open/close
##     

                   
    # built array with valve mag open / close times 
    for i in range(1, len(sheet)-1):   # note first and last entry are needed for algorithm
        prerow=sheet[i-1]
        row=sheet[i]
        postrow=sheet[i+1]
  
        magnify = float(row[2])
        magtime=0

        if magnify >3000 and row[3]:   # start of acquisition cycle
            if row[0] == postrow[0]:   # check if same day 
               magtime = ( time2sec(postrow[1]) - time2sec(row[1]) )
            else:
               magtime = (86400- time2sec(row[1]) ) # day changed

##       #H50*(A51<>A50)*B51*24*60
        if  float( prerow[2] ) >3000  and prerow[3] and row[0] != prerow[0]: #chk for date change, add leftover 
            magtime += time2sec(row[1] ) # previous changed
        magtimes.append(magtime)
        numexplows.append( 1*(magnify < 20000 and row[3]) )
        numexphighs.append( 1*(magnify > 20000 and row[3]) )     
        
    # At this point we have array dates, magtimes
    # next is to sum all secs from open/close data from one day into one number per day

    dates.pop(0)
    dates.pop(-1)

    day = dates[0]               # day is first day that will be summed 
    magtime = 0                  # magtime.pop(0)
    explow  = 0
    exphigh = 0    
   
    # merge entries of one day into one number          
    for date in dates:

        if date > enddate:
            mag[date] = 0
            exps[date]= 0
            
        else:      
            if  date == day:
                magtime +=     magtimes.pop(0)
                explow  +=     numexplows.pop(0)                
                exphigh +=     numexphighs.pop(0)


            if  date > day:  # start next day
                mag[day] = min(magtime, opensec[day]) # column has to be open during prod time
                magtime = magtimes.pop(0)  # first value for next day
                
                exps[day] = exphigh     # number of exposures durng this day
                exphigh   = 1*numexphighs.pop(0)

                day = date
            
    # finally day 31st has to be added
    if date > enddate:
        mag[day] = 0 
    else:
        mag[day] = min(magtime, opensec[day]) # column has to be open during prod time
##


    return (opensec, closedsec, cryo, mag, exps, activemonth )



######################################################

def lookup_month(nr):
   switcher = {
      1 : 'January',
      2 : 'February',
      3 : 'March',
      4 : 'April',
      5 : 'May',
      6 : 'June',
      7 : 'July',
      8 : 'August',
      9 : 'September',
      10: 'October',
      11: 'November',
      12: 'December'
   }
   return switcher.get(nr, 'January')
      

def lookup_microscope(argument):
    switcher = {
        'k1': 'Krios 1',
        'k2': 'Krios 2',
        'k3': 'Krios 3',
        'k4': 'Krios 4',
        'k5': 'Krios 5',
        'k6': 'Krios 6',
        'k7': 'Krios 7',
        'k8': 'Glacios'             
    }
    return switcher.get(argument, 'Krios 1')

def lookup_graph(argument):
    switcher = {
        'ln2k1': (all_times[1], [y - 310 for y in all_ln2s[1]], "Nett weight [lb.] LN2 tank Krios 1"), #    
        'ln2k2': (all_times[2], [y - 310 for y in all_ln2s[2]], "Nett weight [lb.] LN2 tank Krios 2"), #     
        'ln2k3': (all_times[3], [y - 310 for y in all_ln2s[3]], "Nett weight [lb.] LN2 tank Krios 3"), #     
        'ln2k4': (all_times[4], [y - 310 for y in all_ln2s[4]], "Nett weight [lb.] LN2 tank Krios 4"), #     
        'ln2k5': (all_times[5], [y - 310 for y in all_ln2s[5]], "Nett weight [lb.] LN2 tank Krios 5"), #     
        'ln2k6': (all_times[6], [y - 310 for y in all_ln2s[6]], "Nett weight [lb.] LN2 tank Krios 6"), #     
        'ln2k7': (all_times[7], [y - 310 for y in all_ln2s[7]], "Nett weight [lb.] LN2 tank Krios 7"), #    
        'ln2k8': (all_times[8], [y - 310 for y in all_ln2s[8]], "Nett weight [lb.] LN2 tank Glacios"), #

        'fr1'  : (all_times[9], all_temps[9], "Temperature freezer [°C]"), #
        
        'humk1': (all_times[10], all_hums[10], "Humidity [%] Krios 1"), # 
        'humk2': (all_times[11], all_hums[11], "Humidity [%] Krios 2"), #    
        'humk3': (all_times[12], all_hums[12], "Humidity [%] Krios 3"), #    
        'humk4': (all_times[13], all_hums[13], "Humidity [%] Krios 4"), #    
        'humk5': (all_times[14], all_hums[14], "Humidity [%] Krios 5"), #    
        'humk6': (all_times[15], all_hums[15], "Humidity [%] Krios 6"), #
        'humk7': (all_times[16], all_hums[16], "Humidity [%] Krios 7"), #
        'humk8': (all_times[17], all_hums[17], "Humidity [%] Glacios"), #
        'humk11':(all_times[18], all_hums[18], "Humidity [%] NCCAT chiller@kitchen"), #
        'humk12':(all_times[29], all_hums[29], "Humidity [%] Aquilos, Glacios, Krios 4 compressor room"), #
        'humk14':(all_times[36], all_hums[36], "Humidity [%] SEMC control room"), #
        'humk18':(all_times[37], all_hums[37], "Humidity [%] krios 5, 6 compressor room"), #

        'tempk1': (all_times[10], all_temps[10], "Temperature [°F] Krios 1"), #
        'tempk2': (all_times[11], all_temps[11], "Temperature [°F] Krios 2"), #
        'tempk3': (all_times[12], all_temps[12], "Temperature [°F] Krios 3"), #
        'tempk4': (all_times[13], all_temps[13], "Temperature [°F] Krios 4"), #
        'tempk5': (all_times[14], all_temps[14], "Temperature [°F] Krios 5"), #
        'tempk6': (all_times[15], all_temps[15], "Temperature [°F] Krios 6"), #
        'tempk7': (all_times[16], all_temps[16], "Temperature [°F] Krios 7"), #
        'tempk8': (all_times[17], all_temps[17], "Temperature [°F] Glacios"), #
        'tempk11':(all_times[18], all_temps[18], "Temperature [°F] NCCAT chiller@kitchen"), #
        'tempk12':(all_times[29], all_temps[29], "Temperature [°F] Aquilos, Glacios, Krios 4 compressor Room"), #
        'tempk14':(all_times[36], all_temps[36], "Temperature [°F] SEMC control room"), #
        'tempk18':(all_times[37], all_temps[37], "Temperature [°F] Krios 5, 6 compressor Room"), #
        
        'tempk21': (all_pHtimes[1], all_pHtemps[1], "Chiller temperature [°F] Krios 1"), #
        'tempk22': (all_pHtimes[2], all_pHtemps[2], "Chiller temperature [°F] Krios 2"), #
        'tempk23': (all_pHtimes[3], all_pHtemps[3], "Chiller temperature [°F] Krios 3"), #
        'tempk24': (all_pHtimes[4], all_pHtemps[4], "Chiller temperature [°F] Krios 4"), #   
        
        'volt1'  : (all_times[21], all_hums[21], "Facility voltage [V.]"), #
        'duty1'  : (all_times[35], all_hums[35], "Aquilos, Glacios, Krios 4 compressor vib [Hz]"), #
        'duty2'  : (all_times[38], all_hums[38], "Krios 5, 6 compressor vib [Hz]"), #

        'emik1x' : (all_times[23], all_ln2s[23], "DC field [uT] - X(blue), Y(orange) Z(green)\n - Krios 1"), #
        'emik1y' : (all_times[23], all_temps[23], "DC field [uT] - Y - Krios 1"), #
        'emik1z' : (all_times[23], all_hums[23], " \nKrios 1\nDC field [uT] \n X(blue), Y(orange) Z(green) "), #
        'emik2x' : (all_times[24], all_ln2s[24], "DC field [uT] - X(blue), Y(orange) Z(green)\n - Krios 2"), #
        'emik2y' : (all_times[24], all_temps[24], "DC field [uT] - Y - Krios 1"), #
        'emik2z' : (all_times[24], all_hums[24], " \nKrios 2\nDC field [uT] \n X(blue), Y(orange) Z(green) "), #
        'emik3x' : (all_times[25], all_ln2s[25], "DC field [uT] - X(blue), Y(orange) Z(green)\n - Krios 3"), #
        'emik3y' : (all_times[25], all_temps[25], "DC field [uT] - Y - Krios 1"), #
        'emik3z' : (all_times[25], all_hums[25], "-\nKrios 3\nDC field [uT] \n X(blue), Y(orange) Z(green) "), #
        'emik4x' : (all_times[26], all_ln2s[26], "DC field [uT] - X(blue), Y(orange) Z(green)\n - Krios 4"), #
        'emik4y' : (all_times[26], all_temps[26], "DC field [uT] - Y - Krios 1"), #
        'emik4z' : (all_times[26], all_hums[26], "\nKrios 4\nDC field [uT] \n X(blue), Y(orange) Z(green) "), #
        'emik5x' : (all_times[27], all_ln2s[27], "DC field [uT] - X(blue), Y(orange) Z(green)\n - Krios 5"), #
        'emik5y' : (all_times[27], all_temps[27], "DC field [uT] - Y - Krios 1"), #
        'emik5z' : (all_times[27], all_hums[27], "\nKrios 5\nDC field [uT] \n X(blue), Y(orange) Z(green) "), #
        'emik6x' : (all_times[28], all_ln2s[28], "DC field [uT] - X(blue), Y(orange) Z(green)\n - Krios 6"), #
        'emik6y' : (all_times[28], all_temps[28], "DC field [uT] - Y - Krios 1"), #
        'emik6z' : (all_times[28], all_hums[28], " \nKrios 6\nDC field [uT] \n X(blue), Y(orange) Z(green) "), #
        'emik7x' : (all_times[33], all_ln2s[33], "DC field [uT] - X(blue), Y(orange) Z(green)\n - Krios 7"), #
        'emik7y' : (all_times[33], all_temps[33], "DC field [uT] - Y - Krios 7"), #
        'emik7z' : (all_times[33], all_hums[33], " \nKrios 7\nDC field [uT] \n X(blue), Y(orange) Z(green) "), #


        'pHk21': (all_pHtimes[1], all_pHs[1], "Chiller pH [log] Krios 1"), #
        'pHk22': (all_pHtimes[2], all_pHs[2], "Chiller pH [log] Krios 2"), #
        'pHk23': (all_pHtimes[3], all_pHs[3], "Chiller pH [log] Krios 3"), #
        'pHk24': (all_pHtimes[4], all_pHs[4], "Chiller pH [log] Krios 4"), #
        'pHk25': (all_pHtimes[5], all_pHs[5], "Chiller pH [log] Krios 5"), #
        'pHk26': (all_pHtimes[6], all_pHs[6], "Chiller pH [log] Krios 6"), #
        'pHk27': (all_pHtimes[7], all_pHs[7], "Chiller pH [log] Krios 7"), #
        'pHk28': (all_pHtimes[8], all_pHs[8], "Chiller pH [log] Glacios"), # Glacios 7th pos for now
        
        'Raspb54' : 22
        }

    # lookup full name
    return switcher.get(argument, 1)


def data2file(data, fname):
    with open (fname, "w") as fo:

       for row in data:
          for c in row:
             fo.write(str(c))
             fo.write(',')
          fo.write('\n')
    return()


def data4romfile(fname, conv2int):
    all_krios=[]
    if Path(fname).is_file():
        with open(fname) as f:
            content = list(f)    # content is all data from one file
        #  built matrix row by row
        for krios in content:    # krios is data from 1 krios, list of strings sep by , end by \n
            items = krios.split(',')
            del(items[-1])   #  last item is empty '\n'
            if conv2int:
               row = [int(item) for item in items]
            else:
               row = items
            all_krios.append(row)
    else:
       print('\n no init load file found!!\nfname is: ', fname)
       time.sleep(10)
    return(all_krios)


def time2sec(timestr):

    hours = int(timestr[0:2])
    minutes = int(timestr[3:5])
    seconds = int( float( timestr[6:12] ) + 0.5)

    minutes += hours * 60
    seconds += minutes*60

    return(seconds)

def look4data(fname):
    # create content (list of strings) of all HM entries
    with open(fname) as f:
      content = list(f)

    #  get rid of the 12 header lines
    for h in range(12):
      del content[0]   

    return(content)



############################################

# create worker threads
def create_workers():

   # update sensor data
   thr = myThread(refresh_sensors)
   #thr.daemon = True
   thr.start()

   # start UI
   thr = myThread(UI)
   #thr.daemon = True
   thr.start()

def refresh_sensors():
   
   # init data for graphs pie and column uptime 
   global open_krios, closed_krios, cryo_krios, mag_krios, exps_krios, down_krios, month_krios, all_status, all_steps

##
##   # reload processed data if exists  
##   open_krios      = data4romfile('July_open_krios.csv')
##   closed_krios    = data4romfile('July_closed_krios.csv')
##   cryo_krios      = data4romfile('July_cryo_krios.csv')
##   mag_krios       = data4romfile('July_mag_krios.csv')
##   down_krios      = data4romfile('July_down_krios.csv')
##

   month  = time.localtime(time.time()).tm_mon
   #month = 8


   # fill positions of all 1D/2D array
   row         = 32 # max day in month is 31 like Dec 31st
   col         = 9  # 8 systems. Row 0 is void
   month_krios = [0 for _ in range(col)]
   open_krios  = [ [0 for _ in range(row)] for _ in range(col)]
   closed_krios= [ [0 for _ in range(row)] for _ in range(col)] # [row]*col
   cryo_krios  = [ [0 for _ in range(row)] for _ in range(col)] # [row]*col
   mag_krios   = [ [0 for _ in range(row)] for _ in range(col)] # [row]*col
   exps_krios  = [ [0 for _ in range(row)] for _ in range(col)] # [row]*col
   
   conv2int    = True # file with integer info
   down_krios  = data4romfile('down_krios.csv', conv2int)

   # load existing comments of the current month
   path    = os.path.join(os.getcwd(), 'Appdata/')
   if False: # os.path.exists(path):

      conv2int    = False # import all status info as txt
      all_status   = data4romfile(path+lookup_month(month) +'_calls_krios.csv', conv2int)

      all_steps   = data4romfile(path+lookup_month(month) +'_steps_krios.csv', conv2int)

   else:
      #os.mkdir(path)
      all_status   = [ ["In use" for _ in range(row)] for _ in range(col)] # [row]*col
      all_steps   = [ ["-" for _ in range(row)] for _ in range(col)] # [row]*col
      data2file(all_status, path + lookup_month(month) +'_calls_krios.csv')
      data2file(all_steps, path + lookup_month(month) +'_steps_krios.csv')
      

   for req in range(1,9):
      print('\n **** ****' * 3)
         
      opensec, closedsec, cryo, mag, exps, month = uptime_stats('k'+str(req))
      
      open_krios[req]   = (opensec)
      closed_krios[req] = (closedsec)
      cryo_krios[req]   = (cryo)
      mag_krios[req]    = (mag)
      exps_krios[req]   = (exps)
      month_krios[req]  = (month)

   # save processed data as csv file that can be imported as list
   data2file(open_krios, path + lookup_month(month) +'_open_krios.csv')
   data2file(closed_krios, path + lookup_month(month) +'_closed_krios.csv')
   data2file(cryo_krios, path + lookup_month(month) +'_cryo_krios.csv')
   data2file(mag_krios, path + lookup_month(month) +'_mag_krios.csv')
   data2file(exps_krios, path + lookup_month(month) +'_exps_krios.csv')

   # data for graphs facility overview
   init_numsamples = 5001
   global all_times, all_temps, all_hums, all_ln2s
   all_times, all_temps, all_hums, all_ln2s = [[]], [[]], [[]], [[]]

   all_systems = ['Krios 1',  #1
                  'Krios 2',  #2
                  'Krios 3',  #3
                  'Krios 4',  #4
                  'Krios 5',  #5
                  'Krios 6',  #6
                  'Krios 7',  #7
                  'Glacios',  #8
                  'Raspb 0',  #9
                  'Raspb 1', #10
                  'Raspb 2', #11
                  'Raspb 3', #12
                  'Raspb 4', #13
                  'Raspb 5', #14
                  'Raspb 6', #15
                  'Raspb 7', #16
                  'Raspb 8', #17
                  'Raspb11', #18
                  'Raspb21', #19
                  'Raspb22', #20
                  'Raspb23', #21
                  'Raspb24', #22
                  'Raspb31', #23
                  'Raspb32', #24
                  'Raspb33', #25
                  'Raspb34', #26
                  'Raspb35', #27
                  'Raspb36', #28
                  'Raspb12', #29
                  'Raspb25', #30
                  'Raspb26', #31
                  'Raspb28', #32                                    
                  'Raspb37', #33
                  'Raspb27', #34
                  'Raspb52', #35
                  'Raspb14', #36
                  'Raspb18', #37
                  'Raspb58'  #38                 
                  ]

   # initial fill of standard arrays with db data
   for system in all_systems:
       times, temps, hums, ln2s = init_sensordata(system, init_numsamples)

       all_times.append(times)
       all_temps.append(temps)
       all_hums.append(hums)
       all_ln2s.append(ln2s)

   # initial fill of pH arrays with db data

   init_numsamples = 5001
   global all_pHtimes, all_pHtemps, all_pHs
   all_pHtimes, all_pHtemps, all_pHs = [[]], [[]], [[]]
   
   for system in ['Raspb21', 'Raspb22', 'Raspb23', 'Raspb24', 'Raspb25', 'Raspb26', 'Raspb27', 'Raspb28']:
      pHtimes, pHtemps, pHs = init_pHdata(system, numsamples)
      all_pHtimes.append(pHtimes)
      all_pHtemps.append(pHtemps)
      all_pHs.append(pHs)
               
   # subsequent update of arrays with db data
   print('\n Starting sensor monitor mode \n')

   counter = 1
   while True:
       for i, system in enumerate (all_systems):

           if len (all_times[i+1]): # if exist: get time of last sensor update
               last = (all_times[i+1][-1])

           else:
               last = int(time.time())
               print('no new sensor data for system: '+ system)

           # adding new data to array
           times, temps, hums, ln2s = new_sensordata(system, last)
           all_times[i+1]+= (times)
           all_temps[i+1]+=(temps)
           all_hums[i+1]+= (hums)
           all_ln2s[i+1]+= (ln2s)

           if system == 'Raspb21' and not(counter % 10): # make time scale 10x by only selecting every 10th entry. 
               all_pHtimes[1]+=(times)
               all_pHtemps[1]+=(temps)               
               all_pHs[1]    += (hums)
           elif system == 'Raspb22' and not(counter % 10): # make time scale 10x by only selecting every 10th entry. 
               # pHtimes, pHs = init_pHdata(system, numsamples)
               all_pHtimes[2]+=(times)
               all_pHtemps[2]+=(temps)               
               all_pHs[2]    += (hums)
           elif system == 'Raspb23' and not(counter % 10): # make time scale 10x by only selecting every 10th entry. 
               # pHtimes, pHs = init_pHdata(system, numsamples)
               all_pHtimes[3]+=(times)
               all_pHtemps[3]+=(temps)                              
               all_pHs[3]    += (hums)
           elif system == 'Raspb24' and not(counter % 10): # make time scale 10x by only selecting every 10th entry. 
               # pHtimes, pHs = init_pHdata(system, numsamples)
               all_pHtimes[4]+=(times)
               all_pHtemps[4]+=(temps)                              
               all_pHs[4]    += (hums)
           elif system == 'Raspb25' and not(counter % 10): # make time scale 10x by only selecting every 10th entry. 
               # pHtimes, pHs = init_pHdata(system, numsamples)
               all_pHtimes[5]+=(times)
               all_pHtemps[5]+=(temps)                              
               all_pHs[5]    += (hums)
           elif system == 'Raspb26' and not(counter % 10): # make time scale 10x by only selecting every 10th entry. 
               # pHtimes, pHs = init_pHdata(system, numsamples)
               all_pHtimes[6]+=(times)
               all_pHtemps[6]+=(temps)                              
               all_pHs[6]    += (hums)               
           elif system == 'Raspb27' and not(counter % 10): # make time scale 10x by only selecting every 10th entry. 
               # pHtimes, pHs = init_pHdata(system, numsamples)
               all_pHtimes[7]+=(times)
               all_pHtemps[7]+=(temps)                              
               all_pHs[7]    += (hums)
           elif system == 'Raspb28' and not(counter % 10): # make time scale 10x by only selecting every 10th entry. 
               # pHtimes, pHs = init_pHdata(system, numsamples)
               all_pHtimes[8]+=(times)
               all_pHtemps[8]+=(temps)                              
               all_pHs[8]    += (hums)                 

           if i < 8 : # Krios 1 is system nr 0, Glacios is system nr 7
               if look4log(i+1):
               
                  opensec, closedsec, cryo, mag, exps, month = uptime_stats('k'+str(i+1))
                  open_krios[i+1]   = (opensec)
                  closed_krios[i+1] = (closedsec)
                  cryo_krios[i+1]   = (cryo)
                  mag_krios[i+1]    = (mag)
                  exps_krios[i+1]   = (exps)
                  month_krios[i+1]  = (month)

                  # save processed data as csv file that can be imported as list
                  data2file(open_krios, lookup_month(month) +'_open_krios.csv')
                  data2file(closed_krios, lookup_month(month) +'_closed_krios.csv')
                  data2file(cryo_krios, lookup_month(month) +'_cryo_krios.csv')
                  data2file(mag_krios, lookup_month(month) +'_mag_krios.csv')
                  data2file(exps_krios, lookup_month(month) +'_exps_krios.csv')

               print('\n*** check logs finished for system: ' + str(i+1)+ '***\n')   


       pause = 5
       while pause:
           time.sleep(0.9)
           pause = int(time.time())%60
           
       counter+=1
       print("\n going in next cycle for fresh sensors \n ")
###
       
def UI():

   for t in range (10):
      print( '\n-- Downloading data for graphs. Remaining: %d seconds --' %((10-t)*3) )
      time.sleep(3)
      
   app.run(host='0.0.0.0', port = 80, debug=False)
   

#############################


if __name__ == "__main__":
 
    create_workers()

