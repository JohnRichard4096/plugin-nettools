import dns


def nslookup_all_records(domain):
    record_types = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "SRV"]
    results = []

    for record_type in record_types:
        try:
            answers = dns.resolver.resolve(domain, record_type)
            results.append(f"-----记录类型: {record_type}-----")
            for answer in answers:
                results.append(f"{answer}")
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            results.append("---无---")
        except Exception as e:
            results.append(f"错误 - {str(e)}")

    return results
