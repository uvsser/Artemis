HELP=r"""
Arguments:
  TARGET                  Target IP or resolvable hostname
  -p, --ports             Ports to scan  (default: 1-1024)
                          e.g.  80,443   or   1-1024   or   22,80,1000-2000
  -c, --concurrency       Max simultaneous connections  (default: 500)
  -t, --timeout           Socket timeout in seconds     (default: 1.0)
Commands:
  help                    Show this help message
  exit / quit             Quit Artemis
Examples:
  scan 192.168.1.1
  scan scanme.nmap.org -p 22,80,443
  scan 10.0.0.1 -p 1-1024 -c 300 -t 1.5"""