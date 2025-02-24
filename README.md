# AirTrafficRadar
A desktop application for real-time airport traffic monitoring featuring METAR data, live webcams and their live ATC radio, and ADSB-Exchange integration. 
Built with Python and PyQt6.
There is no real benefit of this app, i just wanted to create a more interesting "Panel" for using already existing services. Just for fun :) 


## Features
- Live METAR data display (http://tgftp.nws.noaa.gov/)
- Airport webcam integration (youtube live streams)
- ADSB-Exchange radar view (https://globe.adsbexchange.com/) (works with PremiumAccount/Login aswell, then without ads)
- Configurable airport database (airport.json file)
- Dark mode interface (GUI matches ADSB-Exchange)


## Prerequisites
- **Python** 3.9.7 x64
- **VLC Media Player installed**
- I only tested it on windows 11 x64


## Windows Release
Of course you could run it with python directly (just download the project and run the AutoTrafficRadar.py, but if youre like me and want a exe file:
You can download a working version for windows under the release section. (zip file containing the exe + a folder named "_internal" - you need both in the same directory)
Just unpack the zip file to a folder and run the exe. 
BUT: because MS Defender thinks its malware (atleast mine does, i guess because of a lacking signature), heres a description how you can create the *.exe file on your own if you dont trust me :)

- Install python 3.9.7 x64 & restart your computer
- run "pip install auto-py-to-exe" in your powershell to install autopytoexe
- download my project from github and then navigate to the project folder "AirTrafficRadar" using powershell
- Then run: "pyinstaller --noconfirm --onedir --windowed --add-data "airports.json;." AirTrafficRadar.py"
- this will take a while and will create the *.exe for you. 


## Disclaimer
This app was built mostly with AI as a fun project for a friend. Im only using publicly avaible data (see features) and combine them in one GUI.
Do whatever floats your boat with it ^^


## Screenshots
![image](https://github.com/user-attachments/assets/4f52967e-102b-4705-9321-704dc87ec946)
![image](https://github.com/user-attachments/assets/88cc4c3c-87bf-4336-925f-e0ac7edf9b94)
![image](https://github.com/user-attachments/assets/b4016236-c71f-4ef7-ba04-58e0bb4409ac)
