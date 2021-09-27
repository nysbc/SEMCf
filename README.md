
# Preparing the Raspberry Pi #
### Install the latest Raspberry Pi OS
Follow the instructions on this page to get Raspberry Pi OS running
https://www.raspberrypi.org/downloads/raspberry-pi-os/


### Update and Upgrade Packages 
    
    sudo apt-get update
    sudo apt-get upgrade

###  install Python 3 ###

	Use PI menu \[preference]\[Add / remove software] and install IDLE


### install pip and wheel  ###
 
       sudo apt-get install python3-pip
       
### install temperature /humidity sensor ###
       sudo pip3 install Adafruit_DHT


# Download sample code.
    
    cd ~
    git clone https://github.com/nysbc/SEMCf

### to autostart TemHum.py software ###
       sudo crontab -e
       Add:
@reboot sudo python /home/pi/temhum/temhum.py >/home/pi/logs/cronlog.txt



# I2C MODE ? communication protocol used for the pH sensor #


### Enable I2C bus on the Raspberry Pi ###

Enable I2C bus on the Raspberry Pi by following this:

https://learn.adafruit.com/adafruits-raspberry-pi-lesson-4-gpio-setup/configuring-i2c

You can confirm that the setup worked and sensors are present with 
sudo i2cdetect -y 1





### Test Sensor ###
    
Run the sample code below:
    
    cd ~/Raspberry-Pi-sample-code
    sudo python i2c.py

When the code starts up a list of commands will be shown.

For more details on the commands & responses, please refer to the Datasheets of the Atlas Scientific Sensors.


