// +------------------------------------------------------------------+
// |             ____ _               _        __  __ _  __           |
// |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
// |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
// |           | |___| | | |  __/ (__|   <    | |  | | . \            |
// |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
// |                                                                  |
// | Copyright Mathias Kettner 2014             mk@mathias-kettner.de |
// +------------------------------------------------------------------+
//
// This file is part of Check_MK.
// The official homepage is at http://mathias-kettner.de/check_mk.
//
// check_mk is free software;  you can redistribute it and/or modify it
// under the  terms of the  GNU General Public License  as published by
// the Free Software Foundation in version 2.  check_mk is  distributed
// in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
// out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
// PARTICULAR PURPOSE. See the  GNU General Public License for more de-
// ails.  You should have  received  a copy of the  GNU  General Public
// License along with GNU Make; see the file  COPYING.  If  not,  write
// to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
// Boston, MA 02110-1301 USA.

#include <stdlib.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <sstream>
#include <vector>
#include <netdb.h>

using namespace std;

#ifndef AF_LOCAL
#define   AF_LOCAL AF_UNIX
#endif
#ifndef PF_LOCAL
#define   PF_LOCAL PF_UNIX
#endif

void usage()
{
    printf("Usage: check_mkevents [-s SOCKETPATH] [-H REMOTE:PORT] [-a] HOST [APPLICATION]");
    printf("\n -a    do not take into account acknowledged events.\n");
    printf(" HOST  may be a hostname, and IP address or hostname/IP-address.\n");
}


string prepare_hostname_regex(const char *s)
{
    const char *scan = s;
    string result = "";
    while (*scan) {
        if (strchr("[](){}^$.*+?|\\", *scan)) {
            result += "\\";
            result += *scan;
        }
        else if (*scan == '/')
            result += "|";
        else
            result += *scan;
        scan ++;
    }
    return result;
}


int main(int argc, char** argv)
{
    // Parse arguments
    char *host                = NULL;
    char *remote_host         = NULL;
    char *remote_hostaddress  = NULL;
    char  remote_hostipaddress[64];
    int   remote_port         = 6558;
    char *application         = NULL;
    bool  ignore_acknowledged = false;
    char  unixsocket_path[1024];
    unixsocket_path[0] = 0;

    int argc_count = argc;
    for (int i = 1; i < argc ; i++) {
        if (!strcmp("-H", argv[i]) && i < argc + 1) {
            remote_host = argv[i+1];
            i++;
            argc_count -= 2;
        }
        else if (!strcmp("-s", argv[i]) && i < argc + 1) {
            strcpy(unixsocket_path, argv[i+1]);
            i++;
            argc_count -= 2;
        }
        else if (!strcmp("-a", argv[i])) {
            ignore_acknowledged = true;
            argc_count--;
        }
        else if (argc_count > 2) {
            host = argv[i];
            application = argv[i+1];
            break;
        }
        else if (argc_count > 1) {
            host = argv[i];
            break;
        }
    }

    if (!host) {
        usage();
        exit(3);
    }

    // Get omd environment
    if (!unixsocket_path[0] && !remote_host) {
        char *omd_path = getenv("OMD_ROOT");
        if (omd_path)
            snprintf(unixsocket_path, sizeof(unixsocket_path), "%s/tmp/run/mkeventd/status", omd_path);
        else {
            printf("UNKNOWN - OMD_ROOT is not set, no socket path is defined.\n");
            exit(3);
        }
    }

    if (remote_host) {
        struct hostent *he;
        struct in_addr **addr_list;

        remote_hostaddress = strtok(remote_host, ":");
        if ( (he = gethostbyname(remote_hostaddress) ) == NULL)
        {
            printf("UNKNOWN - Unable to resolve remote host address: %s\n", remote_hostaddress);
            return 3;
        }
        addr_list = (struct in_addr **) he->h_addr_list;
        for(int i = 0; addr_list[i] != NULL; i++)
        {
            strcpy(remote_hostipaddress, inet_ntoa(*addr_list[i]) );
        }

        char *port_str = strtok(NULL, ":");
        if (port_str)
            remote_port = atoi(port_str);
    }

    //Create socket and setup connection
    int sock;
    struct timeval tv;
    if (remote_host) {
        sock = socket(AF_INET, SOCK_STREAM, 0);
        tv.tv_sec = 10;
        setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (struct timeval *)&tv, sizeof(struct timeval));
        // Right now, there is no send timeout..
        // setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (struct timeval *)&tv, sizeof(struct timeval));

        struct sockaddr_in addr;
        memset(&addr, 0, sizeof(addr));
        addr.sin_family = AF_INET;
        inet_aton(remote_hostipaddress, &addr.sin_addr);
        addr.sin_port = htons(remote_port);

        if (0 > connect(sock, (struct sockaddr*) &addr, sizeof(struct sockaddr_in)))
        {
            printf("UNKNOWN - Cannot connect to event daemon via TCP %s:%d (%s)\n",
                   remote_hostipaddress, remote_port, strerror(errno));
            exit(3);
        }
    }
    else {
        sock = socket(PF_LOCAL, SOCK_STREAM , 0);
        if (sock < 0) {
            printf("UNKNOWN - Cannot create client socket: %s\n", strerror(errno));
            exit(3);
        }

        tv.tv_sec = 3;
        setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (struct timeval *)&tv, sizeof(struct timeval));

        struct sockaddr_un addr;
        memset(&addr, 0, sizeof(struct sockaddr_un));
        addr.sun_family = AF_LOCAL;
        strncpy(addr.sun_path, unixsocket_path, sizeof(addr.sun_path));

        if(0 > connect(sock, (struct sockaddr*) &addr, sizeof(struct sockaddr_un))){
            printf("UNKNOWN - Cannot connect to event daemon via UNIX socket %s (%s)\n",
                   unixsocket_path, strerror(errno));
            exit(3);
        }
    }

    // Create query message
    string query_message;
    query_message += "GET events\nFilter: event_host ";
    if (strchr(host, '/')) {
        query_message += "~~ ";
        query_message += prepare_hostname_regex(host);
    }
    else {
        query_message += "=~ ";
        query_message += host;
    }
    query_message += "\nFilter: event_phase in open ack\n";
    query_message += "OutputFormat: plain\n";

    if (application) {
        query_message += "Filter: event_application ~~ ";
        query_message += application;
        query_message += "\n";
    }

    // Send message
    int length = write(sock, query_message.c_str(), query_message.length());

    // Get response
    char response_chunk[4096];
    memset(response_chunk, 0, sizeof(response_chunk));
    stringstream response_stream;
    int read_length;
    while (0 < (read_length = read(sock, response_chunk, sizeof(response_chunk))))
    {
        // replace binary 0 in response with space
        for (int i=0; i<read_length; i++) {
            if (response_chunk[i] == 0)
                response_chunk[i] = ' ';
        }
        response_stream << string(response_chunk, read_length);
        memset(response_chunk, 0, sizeof(response_chunk));
    }
    close(sock);

    // Start processing data
    string line;
    getline(response_stream, line);

    stringstream linestream;
    linestream << line;

    // Get headers
    string token;
    int idx_event_phase = -1;
    int idx_event_state = -1;
    int idx_event_text  = -1;
    int current_index = 0;
    vector<string> headers;
    while (getline(linestream, token, '\x02')) {
        if (!strcmp(token.c_str(), "event_phase"))
            idx_event_phase = current_index;
        else if (!strcmp(token.c_str(), "event_state"))
            idx_event_state = current_index;
        else if (!strcmp(token.c_str(), "event_text"))
            idx_event_text  = current_index;
        headers.push_back(token);
        current_index++;
    }

    // Basic header validation
    if (idx_event_phase == -1 || idx_event_state == -1 || idx_event_text == -1) {
        printf("UNKNOWN - Invalid answer from event daemon\n%s\nQuery was:\n%s\n",
               response_stream.str().c_str(), query_message.c_str());
        exit(3);
    }

    // Get data
    vector< vector<string> > data;
    while (getline(response_stream, line)) {
        if (line.size() < headers.size())
            break; // broken / empty line
        linestream.str("");
        linestream.clear();
        linestream << line;
        vector<string> data_line;
        bool has_data = false;
        while (getline(linestream, token, '\x02')) {
            has_data = true;
            data_line.push_back(token);
        }
        if (has_data)
            data.push_back(data_line);
    }

    // Generate output
    string worst_row_event_text;
    int worst_state              = 0;
    int count                    = 0;
    int unhandled                = 0;

    for (vector< vector<string> >::iterator it = data.begin() ; it != data.end(); ++it) {
        count++;
        const char* p = it->at(idx_event_phase).c_str();
        if (!strcmp(p, "open") || !ignore_acknowledged) {
            int s = atoi(it->at(idx_event_state).c_str());
            if (s == 3) {
                if (worst_state < 2) {
                    worst_state = 3;
                    worst_row_event_text = it->at(idx_event_text);
                }
            } else if ( s >= worst_state ) {
                    worst_state = s;
                    worst_row_event_text = it->at(idx_event_text);
            }
        }
        if (!strcmp(p, "open"))
            unhandled++;
    }

    if (count == 0 && application)
        printf("OK - no events for %s on host %s\n", application, host);
    else if (count == 0)
        printf("OK - no events for %s\n", host );
    else {
        const char* state_text = worst_state == 0 ? "OK" : worst_state == 1 ? "WARN" : worst_state == 2 ? "CRIT" : "UNKNOWN";
        printf("%s - %d events (%d unacknowledged)", state_text, count, unhandled);
        if (worst_row_event_text.length() > 0)
            printf(", worst state is %s (Last line: %s)", state_text, worst_row_event_text.c_str());
        printf("\n");
    }
    return worst_state;
}
