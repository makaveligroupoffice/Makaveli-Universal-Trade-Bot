from performance import PerformanceAnalyzer
from config import Config

def show_network_report():
    analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
    report = analyzer.analyze_central_logs()
    print(report)

if __name__ == "__main__":
    show_network_report()
