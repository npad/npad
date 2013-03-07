import java.awt.Color;
import java.awt.*;
import java.awt.event.*;
import java.net.*;
import java.io.*;
import java.util.*;

import java.awt.Font;
import java.awt.Frame;
import java.awt.Container;
import java.awt.GridBagConstraints;
import java.awt.FlowLayout;
import java.awt.GridBagLayout;
import java.awt.Dimension;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.io.IOException;
import java.net.URL;
import java.util.Properties;

import javax.swing.BorderFactory;
import javax.swing.JApplet;
import javax.swing.JButton;
import javax.swing.JEditorPane;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;

public class DiagClient extends JApplet {
    public final static int VERSION = 0;

    private JButton start_button;
    private DiagnosticThread diagnosticThread = null;
    private String serverName;
    private int controlPort;
    private String defaultRate;
    private String defaultRTT;
    DiagClient parent = this;
    int rtt, rate;


    // for color ideas, see /usr/X11R6/lib/X11/rgb.txt
    private static Color mediumGold = new Color(255, 225, 92);    // (I made the color name up)

    private JTextArea
        logArea  = new JTextArea(10, 40);  // rows, columns

    private JTextField roundTripTimeField, targetRateField, mssField; // filled in later

    // Note: it's important to initialize this with a space,
    // to give the GridBagLayout manager a hint about the height
    // of the label.  If you don't, then the GridBagLayout will
    // assume a zero height, and later, when you set text into
    // the label, the label will grow and cause the layout manager
    // to panic and set the sizes of all the components to their
    // minimums.  Quite ugly.
    private JLabel
        resultUrlLabel = new JLabel(" ");

    private JButton
        startTestButton = new JButton("Start Test");

    private String
        roundTripTimePrompt = "Round Trip Time (msec):",
        targetRatePrompt    = "Target Rate (Mbps):",
        mssPrompt           = "MSS (bytes):";

    private int
        port = 7124,
        roundTripTime,
        targetRate,
        mss;


    public static final int LOCAL = 1;
    public static final int REMOTE = 2;
    public void appendToLogArea(int msgType, String msg) {
        String prefix = "local: ";
        if (msgType == REMOTE)
            prefix = "remote: ";
        logArea.append(prefix + msg + "\n");
        // this is needed to keep the scrollbar knob at the bottom of the track.
        logArea.setCaretPosition(logArea.getDocument().getLength());
    }


    /*
     * Infinite data sink
     */
    private class DiscardThread extends Thread {
        int port;
        String serverName;
        boolean running = false;
        Socket sock;

        DiscardThread(String sName, int port) {
            this.port = port;
            this.serverName = sName;
            this.running = true;
        }

        void finish() {
            running = false;
        }

        boolean getRunning() {
            return running;
        }

        void discard() throws IOException {
            InputStream instream = sock.getInputStream();
            byte[] buf = new byte[128*1024];
            appendToLogArea(LOCAL, "discard thread: listening for discard data on port " + port + "...");
            while ((instream.read(buf) >= 0) && running)
                ;
            appendToLogArea(LOCAL, "discard thread:  stopped listening for discard data.");
        }

        public void run() {
            try {
                sock = new Socket(serverName, port);
            } catch (UnknownHostException e) {
                appendToLogArea(LOCAL, "unknown host: \"" + serverName + "\"" + e.getMessage());
                return;
            } catch (IOException e) {
                appendToLogArea(LOCAL, "error opening discard socket to \"" + serverName + "\": " + e.getMessage());
                return;
            }
            try { discard(); } catch (IOException e) {
                appendToLogArea(LOCAL, "read error: " + e.getMessage());
            } finally {
                try { sock.close(); } catch (IOException e) {
                    appendToLogArea(LOCAL, "error closing discard socket: " + e.getMessage());
                }
            }
        }
    }


    class DiagnosticThread extends Thread {
        TextArea report;
        Socket control_sock = null;
        boolean done = false;
        OutputStream control_out;
        InputStream control_in;
        BufferedReader reader = null;
        String line;
        String serverCommand;
        String tokens[];
        DiscardThread discardThread = null;
        DiagClient parent;

        // constructor
        DiagnosticThread(DiagClient parentDC) {
            this.parent = parentDC;
            report = new TextArea("", 24, 80, TextArea.SCROLLBARS_BOTH);
            report.setFont(new Font("Monospaced", Font.PLAIN, 10));
            report.setEditable(false);
        }

        void closeSockets() {
            done = true;
            if (control_sock != null) {
                try {
                    control_sock.close();
                } catch (IOException e) {
                    appendToLogArea(LOCAL, "error closing control socket: " + e.getMessage());
                }
            }
            if (discardThread != null) {
                discardThread.finish();
                discardThread = null;
            }
        }

        private boolean openControlChannel() {
            showStatus("connecting to " + parent.serverName);
            try {
                control_sock = new Socket(parent.serverName, parent.controlPort);
                control_out = control_sock.getOutputStream();
                control_in = control_sock.getInputStream();
            } catch (Exception e) {
                appendToLogArea(LOCAL, "error connecting control channel: " + e.getMessage());
                return false;
            }
            appendToLogArea(LOCAL, "Control channel to server established.");
            showStatus("Connected to " + parent.serverName);
            return true;
        }

        // Sets up serverCommand and tokens array.
        private boolean getServerMessage() {
            do {
                try {
                    line = reader.readLine();
                } catch (Exception e) {
                    appendToLogArea(LOCAL, "error reading control channel: " + e.getMessage());
                    return false;
                }
                if (line == null) {
                    return false;
                }
                tokens = line.split(" ");
                serverCommand = tokens[0];
            } while (serverCommand.equals(""));
            return true;
        }

        private boolean doVersionHandshake() {
            System.out.println("sending handshake request to server");
            try {
                control_out.write(("handshake " + Integer.toString(VERSION) + "\n").getBytes());
            } catch (IOException e) {
                appendToLogArea(LOCAL, "error writing handshake to control channel: " + e.getMessage());
                return false;
            }
            if (!getServerMessage()) {
                appendToLogArea(LOCAL, "error reading handshake response from control channel");
                return false;
            }
            /* Look for errors first (this can happen on handshake version mismatch. */
            if (serverCommand.equals("error")) {
                appendToLogArea(LOCAL, line);
                return false;
            } else if (!serverCommand.equals("handshake")) {
                appendToLogArea(LOCAL, "client/server protocol error: expected handshake.");
                return false;
            }
            System.out.println("received handshake response from server.");
            String serverVersion = tokens[1];
            /* Check version here if we care. */
            appendToLogArea(LOCAL, "version handshake complete.");
            return true;
        }

        private boolean doServerMessage() {
            if (serverCommand.equals("error")) {
                appendToLogArea(REMOTE, "error: " + line.substring(6));
                return false;
            }
            if (discardThread == null) {     // if we aren't currently running a test
                if (serverCommand.equals("queue_depth")) {
                    int depth = Integer.parseInt(tokens[1]);
                    appendToLogArea(REMOTE, "Waiting for test to start. Currently there are " +
                                    depth + " tests ahead of yours.");
                } else if (serverCommand.equals("listen")) {
//                    appendToLogArea(REMOTE, "please listen for discard data");
                    discardThread = new DiscardThread(serverName, Integer.parseInt(tokens[2]));
                    discardThread.start();
                } else {
                    appendToLogArea(REMOTE, "client/server protocol error: unknown server command: \"" + serverCommand + "\"");
                    return false;
                }
            } else {
                if (serverCommand.equals("info")) {
                    appendToLogArea(REMOTE, line.substring(5));
                } else if (serverCommand.equals("report")) {
                    if (tokens[1].equals("url")) {
                        appendToLogArea(REMOTE, "result URL is \"" + tokens[2] + "\"");
                        /* Show the results in a new browser window. */
                        URL url = null;
                        try {
                            url = new URL(parent.getCodeBase(), tokens[2]);
                        } catch (MalformedURLException m) {
                            appendToLogArea(LOCAL, "error generating results URL: " + m.getMessage());
                        }
                        getAppletContext().showDocument(url, "_top");
                        stop();
                    } else {
                        appendToLogArea(REMOTE, "report \"" + line + "\"");
                    }
                } else {
                    appendToLogArea(REMOTE, "client/server protocol error: unknown server command.");
                    return false;
                }
            }
            return true;
        }

        void doTest() {
            if (!openControlChannel())
                return;
            reader = new BufferedReader(new InputStreamReader(control_in));
            try {
                if (!doVersionHandshake())
                    return;
                showStatus("Testing...");
                String pCommand = "test_pathdiag " +
                    // " --mss=" + mss + " " +
                    rtt + " " + rate;
//                appendToLogArea(LOCAL, "please run \"" + pCommand + "\"");
                try {
                    control_out.write((pCommand + "\n").getBytes());
                } catch (IOException e) {
                    appendToLogArea(LOCAL, "error writing to server: " + e.getMessage());
                    return;
                }
                while (!done && getServerMessage()) {
                    if (!doServerMessage())
                        break;
                }
            } finally {
                closeSockets();
                showStatus("Done");
            }
        }

        public void run() {
            doTest();
            parent.diag_finished();
        }
    }


    private boolean checkInputValues(String rttField, String rateField, String mssField) {
        try {
            rtt  = Integer.parseInt(rttField);
            rate = Integer.parseInt(rateField);
            mss  = Integer.parseInt(mssField);
        } catch (NumberFormatException e) {
            rtt = rate = mss = -1;
        }
        // Let the server worry about the maximums for rate and rtt.
        if (rtt < 1 || rate < 1 || mss < 64 || mss > 65535) {
            appendToLogArea(LOCAL, "error: invalid parameters.\n" +
                            "Valid ranges: 1 < RTT <= 100, 1 < Rate <= 100, 64 < MSS < 65535");
            return false;
        }
        return true;
    }


    // This fires when the user hits the "Start Test" button.
    ActionListener startTestListener =  new ActionListener() {
            public void actionPerformed(ActionEvent e) {
                appendToLogArea(LOCAL, "Start Test");
                if ((diagnosticThread == null) ||   // if we haven't run it yet or
                    !diagnosticThread.isAlive()) {  // we ran it but it died
                    startTestButton.setEnabled(false);
                    if (checkInputValues(roundTripTimeField.getText(),
                                         targetRateField.getText(),
                                         mssField.getText())) {
                        // start a thread that will ask the NPAD server to run a test
                        diagnosticThread = new DiagnosticThread(parent);
                        diagnosticThread.start();
                    }
                }
            }
        };


    public void init() {

        // For debugging, it may be useful to log the environment that
        // client is running in.
        String pluginJavaVendor = "";
        String keys [] = {
            "java.vendor",
            "java.version",
            "os.name",
            "os.arch",
            "os.version"
        };
        String m_key;
        String m_value;
        System.out.println("For this test, the Java plugin environment has these attributes:\n");
        try {
            for (int i = 0; i < keys.length; i++) {
                try {
                    m_key = keys[i];
                    m_value = System.getProperty (m_key);
                    System.out.println(m_key + " = " + m_value);
                    if (m_key.equals("java.vendor")) {
                        pluginJavaVendor = m_value;
                    }
                } catch (SecurityException see) {
                    see.printStackTrace();
                }
            }
        } catch (Exception exception) {
            exception.printStackTrace();
        }

	//################################################## Get some parameters
        try {
            controlPort = Integer.parseInt(getParameter("ControlPort"));
        } catch (Exception e) {
            controlPort = 8000;
        }
	defaultRTT = getParameter("DefaultRTT");
	if (defaultRTT == null) {
	    defaultRTT = "20";
	}
	defaultRate = getParameter("DefaultRate");
	if (defaultRate == null) {
	    defaultRate = "80";
	}
	//	defaultMSS = getParameter("DefaultMSS");
	//	if (defaultMSS == null) {
	//	    defaultMSS = "80";
	//	}

        roundTripTimeField = new JTextField(defaultRTT, 8);
        targetRateField    = new JTextField(defaultRate, 8);
	mssField           = new JTextField("1400", 8);  // not really used

	//################################################## Make it pretty
        serverName = getCodeBase().getHost();

        startTestButton.setForeground(new Color(0, 192, 0)); // dark green
        startTestButton.addActionListener(startTestListener);

        GridBagLayout gridBag = new GridBagLayout();
        GridBagConstraints c = new GridBagConstraints();

        setFont(new Font("Helvetica", Font.PLAIN, 14));
        Container contentPane = getContentPane();
        contentPane.setLayout(gridBag);

        // If we're not an a Mac, set the background color.  Macs
        // display applets with a nice brushed metal background by
        // default, which looks better than a solid color, and since
        // buttons on Macs are oval, if you set a background color you
        // see a background at the edges of the buttons.  The brushed
        // metal is much nicer.
//        if (!pluginJavaVendor.equals("Apple Computer, Inc."))
//            contentPane.setBackground(mediumGold);

        //##################################################  ROW 1  (title)
        c.anchor = GridBagConstraints.CENTER;
        c.gridwidth = GridBagConstraints.REMAINDER;  // last one in this row
        c.insets.bottom = 12;                        // space below the title

	String shortName = serverName;   // Abridge FQDN that are too long
	int MaxNameLen = 30;
	if(shortName.length() > MaxNameLen){
	    int i;
	    for(i = shortName.length(); i >= 0; i--){
		if(i < MaxNameLen-3 && shortName.charAt(i) == '.'){
		    shortName = shortName.substring(0, i) + "...";
		    break;
		}
	    }
	    if (i == 0 ) {
		shortName = shortName.substring(0, MaxNameLen-3) + "...";
	    }
	}

        JLabel title = new JLabel("Test from server " + shortName + " to this machine");
        title.setFont(new Font("SansSerif", Font.PLAIN, 18));
        contentPane.add(title, c);
        c.weightx = 1.0;

        //##################################################  ROW 2 (test parameters and buttons)
        c.anchor = GridBagConstraints.EAST;
        c.gridheight = 1;                  //reset to the default
        c.gridwidth = 1;                   //reset to the default
        c.gridx = GridBagConstraints.RELATIVE;
        c.gridy = GridBagConstraints.RELATIVE;
        c.insets.bottom = 0;               //reset to the default
        c.insets.right = 5;
        contentPane.add(new JLabel(roundTripTimePrompt), c);

        c.anchor = GridBagConstraints.WEST;
        c.insets.right = 0;
        contentPane.add(roundTripTimeField, c);

        c.gridwidth = GridBagConstraints.REMAINDER;  // last one in this row
        contentPane.add(startTestButton, c);

        c.anchor = GridBagConstraints.EAST;
        c.gridwidth = 1;                   //reset to the default
        c.insets.right = 5;
        contentPane.add(new JLabel(targetRatePrompt), c);

        c.anchor = GridBagConstraints.WEST;
        c.insets.right = 0;
        c.gridwidth = GridBagConstraints.REMAINDER;  // last one in this row
        contentPane.add(targetRateField, c);

        // The MSS argument is broken, so we don't need it.
        //      c.anchor = GridBagConstraints.EAST;
        //      c.fill = GridBagConstraints.NONE;
        //      c.insets.right = 5;
        //      c.gridwidth = 1;                   //reset to the default
        //      contentPane.add(new JLabel(mssPrompt), c);
        //      c.anchor = GridBagConstraints.WEST;
        //      c.insets.right = 0;
        //      c.gridwidth = GridBagConstraints.REMAINDER;  // last one in this row
        //      contentPane.add(mssField, c);

        //##################################################  ROW 3 (log label)
        c.fill = GridBagConstraints.HORIZONTAL;
        contentPane.add(new JLabel("Log:"), c);

        //##################################################  ROW 4 (log)
        logArea.setFont(new Font("SansSerif", Font.PLAIN, 10));
        logArea.setBorder(BorderFactory.createLineBorder(Color.black));
        logArea.setEditable(false);
        JScrollPane localScrollPane = new JScrollPane(logArea,
                                                      JScrollPane.VERTICAL_SCROLLBAR_ALWAYS,
                                                      JScrollPane.HORIZONTAL_SCROLLBAR_NEVER);
        contentPane.add(localScrollPane, c);

        System.out.println("init: done initializing ");
    }


    /* Callback for when the diagnostic thread is done */
    private void diag_finished() {
        diagnosticThread = null;
        start_button.setEnabled(true);
    }


    public void stop() {
        if (diagnosticThread != null)
            diagnosticThread.closeSockets();
    }


    public void start() {
    }
}
