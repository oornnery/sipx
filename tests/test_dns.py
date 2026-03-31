"""Tests for sipx._dns (SipResolver, ResolvedTarget)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sipx._dns import ResolvedTarget, SipResolver


class TestResolvedTarget:
    def test_ordering_by_priority(self):
        t1 = ResolvedTarget(priority=10, weight=60, host="a.com", port=5060)
        t2 = ResolvedTarget(priority=5, weight=10, host="b.com", port=5060)
        t3 = ResolvedTarget(priority=20, weight=0, host="c.com", port=5060)
        assert sorted([t1, t2, t3]) == [t2, t1, t3]

    def test_ordering_by_weight_when_priority_equal(self):
        t1 = ResolvedTarget(priority=10, weight=60, host="a.com")
        t2 = ResolvedTarget(priority=10, weight=10, host="b.com")
        assert sorted([t1, t2]) == [t2, t1]

    def test_repr(self):
        t = ResolvedTarget(priority=10, weight=60, host="sip1.example.com", port=5060, transport="UDP")
        r = repr(t)
        assert "UDP" in r
        assert "sip1.example.com" in r
        assert "5060" in r
        assert "pri=10" in r
        assert "w=60" in r

    def test_default_values(self):
        t = ResolvedTarget()
        assert t.priority == 0
        assert t.weight == 0
        assert t.host == ""
        assert t.port == 5060
        assert t.transport == "UDP"


class TestSipResolverResolve:
    def test_resolve_a_record_fallback(self):
        """Without dnspython, should use stdlib socket."""
        resolver = SipResolver()
        # Force no dnspython
        resolver._dns_resolver = None
        with patch("sipx._dns.socket.gethostbyname", return_value="93.184.216.34"):
            targets = resolver.resolve("example.com")
        assert len(targets) == 1
        assert targets[0].host == "93.184.216.34"
        assert targets[0].port == 5060
        assert targets[0].transport == "UDP"

    def test_resolve_a_record_with_transport_tcp(self):
        resolver = SipResolver()
        resolver._dns_resolver = None
        with patch("sipx._dns.socket.gethostbyname", return_value="10.0.0.1"):
            targets = resolver.resolve("example.com", transport="TCP")
        assert targets[0].transport == "TCP"
        assert targets[0].port == 5060

    def test_resolve_a_record_with_transport_tls(self):
        resolver = SipResolver()
        resolver._dns_resolver = None
        with patch("sipx._dns.socket.gethostbyname", return_value="10.0.0.1"):
            targets = resolver.resolve("example.com", transport="TLS")
        assert targets[0].transport == "TLS"
        assert targets[0].port == 5061

    def test_resolve_gaierror_returns_domain_as_is(self):
        import socket

        resolver = SipResolver()
        resolver._dns_resolver = None
        with patch("sipx._dns.socket.gethostbyname", side_effect=socket.gaierror):
            targets = resolver.resolve("nonexistent.example.com")
        assert len(targets) == 1
        assert targets[0].host == "nonexistent.example.com"

    def test_resolve_ip_address_returns_as_is(self):
        resolver = SipResolver()
        resolver._dns_resolver = None
        with patch("sipx._dns.socket.gethostbyname", return_value="192.168.1.1"):
            targets = resolver.resolve("192.168.1.1")
        assert targets[0].host == "192.168.1.1"


class TestSipResolverResolveURI:
    def test_resolve_uri_explicit_port(self):
        resolver = SipResolver()
        targets = resolver.resolve_uri("sip:alice@example.com:5080")
        assert len(targets) == 1
        assert targets[0].host == "example.com"
        assert targets[0].port == 5080
        assert targets[0].transport == "UDP"

    def test_resolve_uri_sips_scheme_defaults_tls(self):
        resolver = SipResolver()
        resolver._dns_resolver = None
        with patch("sipx._dns.socket.gethostbyname", return_value="10.0.0.1"):
            targets = resolver.resolve_uri("sips:bob@secure.example.com")
        assert targets[0].transport == "TLS"

    def test_resolve_uri_transport_tcp_hint(self):
        resolver = SipResolver()
        resolver._dns_resolver = None
        with patch("sipx._dns.socket.gethostbyname", return_value="10.0.0.1"):
            targets = resolver.resolve_uri("sip:alice@example.com;transport=tcp")
        assert targets[0].transport == "TCP"

    def test_resolve_uri_explicit_port_with_sips(self):
        resolver = SipResolver()
        targets = resolver.resolve_uri("sips:alice@example.com:5061")
        assert targets[0].transport == "TLS"
        assert targets[0].port == 5061

    def test_resolve_uri_explicit_port_with_transport_param(self):
        resolver = SipResolver()
        targets = resolver.resolve_uri("sip:alice@example.com:5080;transport=tcp")
        assert targets[0].transport == "TCP"
        assert targets[0].port == 5080


class TestSipResolverSRV:
    def _make_srv_rdata(self, priority, weight, host, port):
        rdata = MagicMock()
        rdata.priority = priority
        rdata.weight = weight
        rdata.target = MagicMock()
        rdata.target.__str__ = lambda _self: f"{host}."
        rdata.port = port
        return rdata

    def _make_mock_dns_modules(self):
        """Create mock dns and dns.resolver modules with real exception classes.

        Returns (dns_package_mock, dns_resolver_mock, patches_dict).
        The code does `import dns.resolver` then `except (dns.resolver.NXDOMAIN, ...)`,
        so dns.resolver must be consistent between sys.modules and attribute access.
        """
        nxdomain = type("NXDOMAIN", (Exception,), {})
        no_answer = type("NoAnswer", (Exception,), {})
        no_nameservers = type("NoNameservers", (Exception,), {})

        resolver_module = MagicMock()
        resolver_module.NXDOMAIN = nxdomain
        resolver_module.NoAnswer = no_answer
        resolver_module.NoNameservers = no_nameservers

        dns_package = MagicMock()
        dns_package.resolver = resolver_module

        patches = {"dns": dns_package, "dns.resolver": resolver_module}
        return dns_package, resolver_module, patches

    def test_resolve_srv_udp(self):
        _, _, patches = self._make_mock_dns_modules()
        resolver = SipResolver()
        mock_dns_resolver = MagicMock()
        rdata = self._make_srv_rdata(10, 60, "sip1.example.com", 5060)
        mock_dns_resolver.resolve.return_value = [rdata]
        resolver._dns_resolver = mock_dns_resolver

        with patch.dict("sys.modules", patches):
            targets = resolver.resolve("example.com", transport="UDP")
        assert len(targets) == 1
        assert targets[0].host == "sip1.example.com"
        assert targets[0].port == 5060
        assert targets[0].transport == "UDP"

    def test_resolve_srv_tcp(self):
        _, _, patches = self._make_mock_dns_modules()
        resolver = SipResolver()
        mock_dns_resolver = MagicMock()
        rdata = self._make_srv_rdata(10, 60, "sip1.example.com", 5060)
        mock_dns_resolver.resolve.return_value = [rdata]
        resolver._dns_resolver = mock_dns_resolver

        with patch.dict("sys.modules", patches):
            targets = resolver.resolve("example.com", transport="TCP")
        assert targets[0].transport == "TCP"

    def test_resolve_srv_tls(self):
        _, _, patches = self._make_mock_dns_modules()
        resolver = SipResolver()
        mock_dns_resolver = MagicMock()
        rdata = self._make_srv_rdata(5, 10, "sips.example.com", 5061)
        mock_dns_resolver.resolve.return_value = [rdata]
        resolver._dns_resolver = mock_dns_resolver

        with patch.dict("sys.modules", patches):
            targets = resolver.resolve("example.com", transport="TLS")
        assert targets[0].transport == "TLS"
        assert targets[0].port == 5061

    def test_resolve_srv_nxdomain_falls_through(self):
        """When SRV raises NXDOMAIN, should fall back to A record."""
        _, resolver_mod, patches = self._make_mock_dns_modules()
        resolver = SipResolver()
        mock_dns_resolver = MagicMock()
        mock_dns_resolver.resolve.side_effect = resolver_mod.NXDOMAIN()
        resolver._dns_resolver = mock_dns_resolver

        with patch.dict("sys.modules", patches):
            with patch("sipx._dns.socket.gethostbyname", return_value="10.0.0.1"):
                targets = resolver.resolve("example.com")
        assert len(targets) >= 1

    def test_resolve_srv_sorted_by_priority(self):
        _, _, patches = self._make_mock_dns_modules()
        resolver = SipResolver()
        mock_dns_resolver = MagicMock()
        rdata1 = self._make_srv_rdata(20, 10, "sip2.example.com", 5060)
        rdata2 = self._make_srv_rdata(5, 60, "sip1.example.com", 5060)
        mock_dns_resolver.resolve.return_value = [rdata1, rdata2]
        resolver._dns_resolver = mock_dns_resolver

        with patch.dict("sys.modules", patches):
            targets = resolver.resolve("example.com", transport="UDP")
        assert targets[0].host == "sip1.example.com"
        assert targets[1].host == "sip2.example.com"

    def test_resolve_srv_no_transport_tries_all(self):
        """When no transport specified, should try UDP, TCP, TLS prefixes."""
        _, _, patches = self._make_mock_dns_modules()
        resolver = SipResolver()
        mock_dns_resolver = MagicMock()
        rdata = self._make_srv_rdata(10, 60, "sip1.example.com", 5060)
        mock_dns_resolver.resolve.return_value = [rdata]
        resolver._dns_resolver = mock_dns_resolver

        with patch.dict("sys.modules", patches):
            targets = resolver.resolve("example.com")
        assert mock_dns_resolver.resolve.call_count == 3
        assert len(targets) >= 1


class TestSipResolverInit:
    def test_init_no_nameservers(self):
        resolver = SipResolver()
        assert resolver._nameservers is None

    def test_init_with_nameservers(self):
        resolver = SipResolver(nameservers=["8.8.8.8"])
        assert resolver._nameservers == ["8.8.8.8"]

    def test_get_resolver_without_dnspython(self):
        resolver = SipResolver()
        with patch.dict("sys.modules", {"dns": None, "dns.resolver": None}):
            # Force fresh attempt
            resolver._dns_resolver = None
            result = resolver._get_resolver()
            # May return None if dnspython not installed
            # Just verify it doesn't crash
