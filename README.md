
## Open Source Reddit

This repository is a fork of the [archived reddit open source](https://github.com/reddit-archive/reddit) code, edited minimally to install on Docker, as the original code has a hard dependance on Ubuntu 14. Most of these modifications originated on the fork/continuation [Saidit](https://github.com/libertysoft3/saidit), which was archived in 2022. Unlike Saidit, the intent of this fork is to provide a buildable/runnable base that is as close to the original Reddit source as is practical. Bug reports and fixes are welcome, but please redirect any feature requests and or modifications to [theorangedit repository](https://github.com/theorangedit/theorangedit) instead.

## Docker Installation

Please see install instructions in the [docker repository](https://github.com/theorangedit/docker-reddit).

## Ubuntu 14 installation (currently untested)

These instructions assume that you have setup a [VirtualBox](https://www.virtualbox.org/wiki/Downloads) virtual machine running [Ubuntu 14.04](http://releases.ubuntu.com/14.04/) with 2+ CPU cores, 4GB of RAM, 30GB of disk space, user 'reddit' and OpenSSH server. Connecting to your virtual machine using SSH is recommended for easy copy and paste.

### Install reddit open source

#### Run the installer

    $ wget --no-check-certificate https://raw.github.com/theorangedit/open-source-reddit/master/install-reddit.sh
    $ chmod +x install-reddit.sh
    $ sudo ./install-reddit.sh

The installer should complete with success message "Congratulations! reddit is now installed". Do not proceed unless you see this message.

#### Option A: start with an empty reddit

    $ cd ~/src/reddit
    $ reddit-run scripts/inject_test_data.py -c 'inject_configuration_data()'
    $ sudo start reddit-job-update_reddits

#### Option B: populate sample user data including posts, comments, and subs

    $ cd ~/src/reddit
    $ reddit-run scripts/inject_test_data.py -c 'inject_test_data()'
    $ sudo start reddit-job-update_reddits

### Install search
 
#### Install Solr

    $ cd ~
    $ sudo apt-get install tomcat7 tomcat7-admin software-properties-common
    $ wget http://archive.apache.org/dist/lucene/solr/4.10.4/solr-4.10.4.tgz
    $ tar -xvzf solr-4.10.4.tgz
    $ sudo mv solr-4.10.4 /usr/share/solr
    $ sudo chown -R tomcat7:tomcat7 /usr/share/solr/example
 
#### Setup Solr and schema

    $ sudo cp /usr/share/solr/example/webapps/solr.war /usr/share/solr/example/solr/
    $ sudo cp /usr/share/solr/example/lib/ext/* /usr/share/tomcat7/lib/
    $ sudo cp /usr/share/solr/example/resources/log4j.properties /usr/share/tomcat7/lib/
    $ sudo cp ~/src/reddit/solr/schema4.xml /usr/share/solr/example/solr/collection1/conf/schema.xml
    $ sudo chown tomcat7:tomcat7 /usr/share/solr/example/solr/collection1/conf/schema.xml
 
#### Setup Tomcat for Solr

    $ sudo sed -i "s/^solr.log=.*$/solr.log=\/usr\/share\/solr/" /usr/share/tomcat7/lib/log4j.properties
 
    $ sudo nano /etc/tomcat7/Catalina/localhost/solr.xml
    # add content:
    <Context docBase="/usr/share/solr/example/solr/solr.war" debug="0" crossContext="true">
      <Environment name="solr/home" type="java.lang.String" value="/usr/share/solr/example/solr" override="true" />
    </Context>
 
    # have tomcat use port 8983 ('solr_port' in example.ini), port 8080 is haproxy
    sudo nano /etc/tomcat7/server.xml
    # edit to set:
    <Connector port="8983" protocol="HTTP/1.1"
 
    # Solr is missing some required stuff:
    $ sudo touch /usr/share/solr/solr.log
    $ sudo mkdir /usr/share/tomcat7/temp
    $ sudo chown tomcat7:tomcat7 /usr/share/solr/solr.log
    $ sudo chown tomcat7:tomcat7 /usr/share/tomcat7/temp
 
    # verify tomcat all good (ignore warnings):
    $ /usr/share/tomcat7/bin/configtest.sh

#### Start solr

    $ sudo service tomcat7 restart
    # any errors logged must be fixed
    $ sudo cat /var/log/tomcat7/catalina.out
    # verify working, these should return html pages:
    $ wget 127.0.0.1:8983
    $ wget 127.0.0.1:8983/solr

#### Index site content

    $ sudo start reddit-job-solr_subreddits
    $ sudo start reddit-job-solr_links

### Configure DNS for reddit.local

To access your reddit open source app, you must be able to resolve https://reddit.local to your virtual machine. First, find the ip address of your virtual machine, then update your 'hosts' file (on your desktop or wherever your web browser is running).

## Next steps

* access reddit open source at https://reddit.local
* login and change the passwords of accounts 'reddit' and 'automoderator', they have default password 'password'