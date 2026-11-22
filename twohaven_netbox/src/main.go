// TwoHaven nätverkslåda: hittar enheterna i hemnätet och stänger av internet för spelkonsoler (Xbox, PlayStation)
// när barnets skärmtid är slut, genom ARP: konsolen får veta att routern finns på en MAC-adress som inte existerar,
// så dess trafik försvinner. Inget annat i nätet påverkas, och utan lådan fungerar allt som vanligt.
//
// Miljövariabler: TH_KEY (familjens Home Assistant-nyckel th_…), TH_URL (standard https://api.twohaven.se), TH_IFACE (valfri).
package main

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

const version = "0.1.0"

var fakeMAC = net.HardwareAddr{0x02, 0x74, 0x68, 0x00, 0x00, 0x01} // finns inte i nätet → trafiken försvinner

type host struct {
	IP       net.IP
	MAC      net.HardwareAddr
	LastSeen time.Time
	Hostname string
}

type state struct {
	mu      sync.Mutex
	hosts   map[string]*host // nyckel: MAC
	blocked map[string]bool  // MAC → spärrad
	gwIP    net.IP
	gwMAC   net.HardwareAddr
	myIP    net.IP
	myMAC   net.HardwareAddr
	network *net.IPNet
	ifIndex int
	ifName  string
	fd      int
}

func htons(v uint16) uint16 { return (v<<8)&0xff00 | v>>8 }

func main() {
	log.SetFlags(log.LstdFlags)
	key := os.Getenv("TH_KEY")
	base := strings.TrimRight(envOr("TH_URL", "https://api.twohaven.se"), "/")
	if !strings.HasPrefix(key, "th_") {
		log.Fatal("TH_KEY saknas – skapa en nyckel i TwoHaven-appen under Mer → Home Assistant")
	}
	s := &state{hosts: map[string]*host{}, blocked: map[string]bool{}}
	if err := s.setup(os.Getenv("TH_IFACE")); err != nil {
		log.Fatal(err)
	}
	log.Printf("TwoHaven nätverkslåda %s på %s (%s, %s), router %s", version, s.ifName, s.myIP, s.myMAC, s.gwIP)
	go s.reader()
	go func() {
		for {
			s.scan()
			time.Sleep(30 * time.Second)
		}
	}()
	go s.spoofLoop()
	time.Sleep(4 * time.Second)
	for {
		interval := s.report(base, key)
		time.Sleep(time.Duration(interval) * time.Second)
	}
}

func envOr(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}

// ---------- Nätverket ----------

func defaultRoute() (iface string, gw net.IP, err error) {
	b, err := os.ReadFile("/proc/net/route")
	if err != nil {
		return "", nil, err
	}
	for _, ln := range strings.Split(string(b), "\n")[1:] {
		f := strings.Fields(ln)
		if len(f) < 3 || f[1] != "00000000" {
			continue
		}
		v, err := strconv.ParseUint(f[2], 16, 32)
		if err != nil {
			continue
		}
		ip := make(net.IP, 4)
		binary.LittleEndian.PutUint32(ip, uint32(v))
		return f[0], ip, nil
	}
	return "", nil, errors.New("hittar ingen standardväg (router)")
}

func (s *state) setup(want string) error {
	name, gw, err := defaultRoute()
	if err != nil {
		return err
	}
	if want != "" {
		name = want
	}
	ifc, err := net.InterfaceByName(name)
	if err != nil {
		return fmt.Errorf("nätverkskort %s: %w", name, err)
	}
	addrs, _ := ifc.Addrs()
	for _, a := range addrs {
		if n, ok := a.(*net.IPNet); ok && n.IP.To4() != nil {
			s.myIP, s.network = n.IP.To4(), &net.IPNet{IP: n.IP.Mask(n.Mask).To4(), Mask: n.Mask}
		}
	}
	if s.myIP == nil {
		return fmt.Errorf("%s har ingen IPv4-adress", name)
	}
	s.gwIP, s.myMAC, s.ifIndex, s.ifName = gw.To4(), ifc.HardwareAddr, ifc.Index, name
	fd, err := syscall.Socket(syscall.AF_PACKET, syscall.SOCK_RAW, int(htons(0x0806)))
	if err != nil {
		return fmt.Errorf("rå socket (kräver NET_RAW): %w", err)
	}
	if err := syscall.Bind(fd, &syscall.SockaddrLinklayer{Protocol: htons(0x0806), Ifindex: ifc.Index}); err != nil {
		return err
	}
	s.fd = fd
	return nil
}

// arp bygger ett ARP-paket i en Ethernet-ram. op 1 = fråga, 2 = svar.
func arp(dstMAC, srcMAC net.HardwareAddr, op uint16, senderMAC net.HardwareAddr, senderIP net.IP, targetMAC net.HardwareAddr, targetIP net.IP) []byte {
	b := make([]byte, 42)
	copy(b[0:6], dstMAC)
	copy(b[6:12], srcMAC)
	binary.BigEndian.PutUint16(b[12:14], 0x0806)
	binary.BigEndian.PutUint16(b[14:16], 1)      // Ethernet
	binary.BigEndian.PutUint16(b[16:18], 0x0800) // IPv4
	b[18], b[19] = 6, 4
	binary.BigEndian.PutUint16(b[20:22], op)
	copy(b[22:28], senderMAC)
	copy(b[28:32], senderIP.To4())
	copy(b[32:38], targetMAC)
	copy(b[38:42], targetIP.To4())
	return b
}

func (s *state) send(frame []byte) {
	var dst [8]byte
	copy(dst[:], frame[0:6])
	_ = syscall.Sendto(s.fd, frame, 0, &syscall.SockaddrLinklayer{Protocol: htons(0x0806), Ifindex: s.ifIndex, Halen: 6, Addr: dst})
}

func (s *state) reader() {
	buf := make([]byte, 1500)
	for {
		n, _, err := syscall.Recvfrom(s.fd, buf, 0)
		if err != nil || n < 42 || binary.BigEndian.Uint16(buf[12:14]) != 0x0806 {
			continue
		}
		mac := net.HardwareAddr(append([]byte(nil), buf[22:28]...))
		ip := net.IP(append([]byte(nil), buf[28:32]...))
		if bytes.Equal(mac, fakeMAC) || bytes.Equal(mac, s.myMAC) || ip.IsUnspecified() || !s.network.Contains(ip) {
			continue
		}
		s.mu.Lock()
		if ip.Equal(s.gwIP) {
			s.gwMAC = mac
		}
		h := s.hosts[mac.String()]
		if h == nil {
			h = &host{MAC: mac}
			s.hosts[mac.String()] = h
		}
		h.IP, h.LastSeen = ip, time.Now()
		s.mu.Unlock()
	}
}

// scan frågar efter varje adress i nätet (högst 1024 st) så att alla enheter svarar.
func (s *state) scan() {
	bc := net.HardwareAddr{0xff, 0xff, 0xff, 0xff, 0xff, 0xff}
	ones, bits := s.network.Mask.Size()
	n := 1 << uint(bits-ones)
	if n > 1024 {
		n = 1024
	}
	base := binary.BigEndian.Uint32(s.network.IP)
	for i := 1; i < n-1; i++ {
		ip := make(net.IP, 4)
		binary.BigEndian.PutUint32(ip, base+uint32(i))
		if ip.Equal(s.myIP) {
			continue
		}
		s.send(arp(bc, s.myMAC, 1, s.myMAC, s.myIP, make(net.HardwareAddr, 6), ip))
		if i%32 == 0 {
			time.Sleep(20 * time.Millisecond)
		}
	}
}

// spoofLoop: var 2:a sekund får spärrade konsoler höra att routern finns på fakeMAC.
func (s *state) spoofLoop() {
	released := map[string]int{}
	for {
		s.mu.Lock()
		gwMAC := s.gwMAC
		type t struct {
			mac net.HardwareAddr
			ip  net.IP
			on  bool
		}
		var todo []t
		for m, on := range s.blocked {
			if h := s.hosts[m]; h != nil && h.IP != nil {
				todo = append(todo, t{h.MAC, h.IP, on})
			}
		}
		s.mu.Unlock()
		for _, x := range todo {
			if x.on {
				s.send(arp(x.mac, s.myMAC, 2, fakeMAC, s.gwIP, x.mac, x.ip))
				released[x.mac.String()] = 0
			} else if gwMAC != nil && released[x.mac.String()] < 5 {
				// Släpp: berätta den riktiga routeradressen några gånger
				s.send(arp(x.mac, s.myMAC, 2, gwMAC, s.gwIP, x.mac, x.ip))
				released[x.mac.String()]++
			}
		}
		time.Sleep(2 * time.Second)
	}
}

// ---------- Servern ----------

type blockItem struct {
	MAC    string `json:"mac"`
	Name   string `json:"name"`
	Block  bool   `json:"block"`
	Reason string `json:"reason"`
}

func (s *state) report(base, key string) int {
	s.mu.Lock()
	devs := []map[string]string{}
	for _, h := range s.hosts {
		if time.Since(h.LastSeen) > 10*time.Minute {
			continue
		}
		if h.Hostname == "" {
			if names, err := net.LookupAddr(h.IP.String()); err == nil && len(names) > 0 {
				h.Hostname = strings.TrimSuffix(names[0], ".")
			}
		}
		devs = append(devs, map[string]string{"mac": h.MAC.String(), "ip": h.IP.String(), "vendor": vendorOf(h.MAC), "hostname": h.Hostname})
	}
	gw := s.gwIP.String()
	s.mu.Unlock()
	body, _ := json.Marshal(map[string]any{"devices": devs, "version": version, "iface": s.ifName, "gateway": gw})
	req, _ := http.NewRequest("POST", base+"/api/ha/v1/netbox", bytes.NewReader(body))
	req.Header.Set("authorization", "Bearer "+key)
	req.Header.Set("content-type", "application/json")
	res, err := (&http.Client{Timeout: 15 * time.Second}).Do(req)
	if err != nil {
		log.Printf("servern svarar inte: %v", err)
		return 30
	}
	defer res.Body.Close()
	var out struct {
		Block    []blockItem `json:"block"`
		Interval int         `json:"interval"`
		Error    string      `json:"error"`
	}
	_ = json.NewDecoder(res.Body).Decode(&out)
	if res.StatusCode != 200 {
		log.Printf("servern: %d %s", res.StatusCode, out.Error)
		return 60
	}
	s.mu.Lock()
	next := map[string]bool{}
	for _, b := range out.Block {
		m := strings.ToLower(b.MAC)
		next[m] = b.Block
		if prev, ok := s.blocked[m]; !ok || prev != b.Block {
			if b.Block {
				log.Printf("Spärrar %s (%s, %s)", b.Name, m, b.Reason)
			} else {
				log.Printf("Släpper %s (%s)", b.Name, m)
			}
		}
	}
	for m, on := range s.blocked {
		if _, ok := next[m]; !ok && on {
			next[m] = false // konsolen är bortkopplad i appen – släpp den
		}
	}
	s.blocked = next
	s.mu.Unlock()
	if out.Interval < 10 {
		out.Interval = 30
	}
	return out.Interval
}

// vendorOf: några vanliga tillverkare (de första tre byten i MAC-adressen) så att konsolerna känns igen i appen.
var vendors = map[string]string{
	"7c:ed:8d": "Microsoft", "98:5f:d3": "Microsoft", "c8:3f:26": "Microsoft", "60:45:bd": "Microsoft", "28:18:78": "Microsoft",
	"30:59:b7": "Microsoft", "c0:33:5e": "Microsoft", "dc:b4:c4": "Microsoft", "58:82:a8": "Microsoft", "bc:83:85": "Microsoft",
	"00:d9:d1": "Sony", "70:9e:29": "Sony", "bc:60:a7": "Sony", "28:3f:69": "Sony", "f8:46:1c": "Sony", "0c:fe:45": "Sony",
	"78:c8:81": "Sony", "00:04:1f": "Sony", "a8:e3:ee": "Sony", "2c:cc:44": "Sony", "5c:84:3c": "Sony", "e8:6e:3a": "Sony",
	"98:b6:e9": "Nintendo", "7c:bb:8a": "Nintendo", "e8:4e:ce": "Nintendo", "04:03:d6": "Nintendo", "58:2f:40": "Nintendo",
	"64:b5:c6": "Nintendo", "a4:38:cc": "Nintendo", "34:af:2c": "Nintendo", "dc:68:eb": "Nintendo", "d4:f0:57": "Nintendo",
}

func vendorOf(m net.HardwareAddr) string {
	if len(m) < 3 {
		return ""
	}
	if m[0]&0x02 != 0 {
		return "slumpad adress"
	}
	return vendors[m[:3].String()]
}
