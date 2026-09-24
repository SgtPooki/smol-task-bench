import Foundation
import FoundationModels

// MARK: - Tools

@Generable
struct GetWeatherArgs {
    var city: String
}
struct GetWeatherTool: Tool {
    var name = "getWeather"
    var description = "Gets the current weather for a city."
    func call(arguments: GetWeatherArgs) async throws -> String {
        let weather: [String: String] = [
            "Tokyo": "Cloudy, 15°C",
            "Paris": "Rainy, 12°C",
            "London": "Foggy, 10°C",
            "Sydney": "Sunny, 25°C",
            "Seattle": "Drizzling, 9°C",
            "Dubai": "Hot, 35°C"
        ]
        return weather[arguments.city] ?? "Unknown city"
    }
}

@Generable
struct LookupOrderArgs {
    var orderId: String
}
struct LookupOrderTool: Tool {
    var name = "lookupOrder"
    var description = "Looks up the status and ETA date of a shopping order by its ID."
    func call(arguments: LookupOrderArgs) async throws -> String {
        let orders: [String: String] = [
            "ORD-101": "Status: Shipped, ETA: 2026-10-01",
            "ORD-102": "Status: Processing, ETA: 2026-10-05",
            "ORD-103": "Status: Delivered, ETA: 2026-09-20",
            "ORD-104": "Status: Cancelled, ETA: N/A",
            "ORD-105": "Status: Backordered, ETA: 2026-11-15",
            "ORD-106": "Status: Shipped, ETA: 2026-10-03"
        ]
        return orders[arguments.orderId] ?? "Order not found"
    }
}

@Generable
struct ConvertCurrencyArgs {
    var amount: Double
    var from: String
    var to: String
}
struct ConvertCurrencyTool: Tool {
    var name = "convertCurrency"
    var description = "Converts an amount of money from one currency to another."
    func call(arguments: ConvertCurrencyArgs) async throws -> String {
        let rates: [String: Double] = [
            "USD": 1.0,
            "EUR": 0.9,
            "GBP": 0.8,
            "JPY": 150.0
        ]
        guard let fromRate = rates[arguments.from.uppercased()],
              let toRate = rates[arguments.to.uppercased()] else {
            return "Unsupported currency"
        }
        let result = arguments.amount / fromRate * toRate
        return String(format: "%.2f %@", result, arguments.to.uppercased())
    }
}

// MARK: - Benchmark Logistics

func areAnyEqual(_ a: Any, _ b: Any) -> Bool {
    if let aDict = a as? [String: Any], let bDict = b as? [String: Any] {
        guard aDict.count == bDict.count else { return false }
        for (k, v) in aDict {
            guard let bVal = bDict[k], areAnyEqual(v, bVal) else { return false }
        }
        return true
    }
    if let aArr = a as? [Any], let bArr = b as? [Any] {
        guard aArr.count == bArr.count else { return false }
        for i in 0..<aArr.count {
            if !areAnyEqual(aArr[i], bArr[i]) { return false }
        }
        return true
    }
    if let aNum = a as? NSNumber, let bNum = b as? NSNumber {
        // NSNumber boolean check
        if String(cString: aNum.objCType) == "c" && String(cString: bNum.objCType) == "c" {
            return aNum.boolValue == bNum.boolValue
        }
        return aNum.doubleValue == bNum.doubleValue
    }
    if let aStr = a as? String, let bStr = b as? String {
        return aStr.lowercased() == bStr.lowercased()
    }
    if let aBool = a as? Bool, let bBool = b as? Bool {
        return aBool == bBool
    }
    return false
}

/// Compare answers on content, not formatting: case, thousands separators, and a trailing ".00".
func normalized(_ s: String) -> String {
    var t = s.lowercased()
    for _ in 0..<3 {  // "1,234,567" needs one pass per separator
        t = t.replacingOccurrences(of: #"(\d),(\d{3})"#, with: "$1$2", options: .regularExpression)
    }
    return t.replacingOccurrences(of: #"(\d)\.00\b"#, with: "$1", options: .regularExpression)
}

func areCallsEqual(_ expected: [[String: Any]], _ actual: [[String: Any]]) -> Bool {
    guard expected.count == actual.count else { return false }
    var matchedActuals = Set<Int>()
    for exp in expected {
        var found = false
        for (i, act) in actual.enumerated() {
            if matchedActuals.contains(i) { continue }
            if let expTool = exp["tool"] as? String, let actTool = act["tool"] as? String,
               expTool == actTool,
               let expArgs = exp["args"] as? [String: Any], let actArgs = act["args"] as? [String: Any],
               areAnyEqual(expArgs, actArgs) {
                found = true
                matchedActuals.insert(i)
                break
            }
        }
        if !found { return false }
    }
    return true
}

struct ToolBench {
    static func main() async {
        let itemsPath = "tasks/tool-calling/items.jsonl"
        let outDir = "results/apple-fm-native"
        let outPath = "\(outDir)/tool-calling.jsonl"

        try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

        guard let content = try? String(contentsOfFile: itemsPath, encoding: .utf8) else {
            print("Failed to read \(itemsPath)")
            return
        }

        let lines = content.split(separator: "\n")
        var exactMatchCount = 0
        var answerContainsCount = 0
        var bothCount = 0
        var totalCount = 0

        var outStream = ""

        let tools: [any Tool] = [GetWeatherTool(), LookupOrderTool(), ConvertCurrencyTool()]

        for line in lines {
            guard let data = line.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let id = obj["id"] as? String,
                  let text = obj["text"] as? String,
                  let expected = obj["expected"] as? [String: Any],
                  let expCalls = expected["calls"] as? [[String: Any]],
                  let expAnswerContains = expected["answerContains"] as? [String] else {
                continue
            }
            totalCount += 1
            print("Running \(id)...")

            let session = LanguageModelSession(tools: tools, instructions: "You are a helpful assistant. Use tools if necessary to answer the user's questions.")

            let startTime = Date()
            var finalAnswer = ""
            var errorStr: String? = nil

            do {
                // greedy, like temperature 0 on the HTTP tracks; no token cap, so runaway loops surface as errors
                let response = try await session.respond(to: text, options: GenerationOptions(samplingMode: .greedy))
                finalAnswer = response.content
            } catch {
                errorStr = String(describing: error)
            }

            let elapsed = Date().timeIntervalSince(startTime)

            var actualCalls: [[String: Any]] = []
            for entry in session.transcript {
                if case .toolCalls(let calls) = entry {
                    for call in calls {
                        let jsonStr = call.arguments.jsonString
                        if let argData = jsonStr.data(using: .utf8),
                           let argDict = try? JSONSerialization.jsonObject(with: argData) as? [String: Any] {
                            actualCalls.append(["tool": call.toolName, "args": argDict])
                        } else {
                            actualCalls.append(["tool": call.toolName, "args": jsonStr])
                        }
                    }
                }
            }

            let callsMatch = errorStr == nil && areCallsEqual(expCalls, actualCalls)  // an errored item never passes

            let containsMatch = errorStr == nil && expAnswerContains.allSatisfy { normalized(finalAnswer).contains(normalized($0)) }

            if callsMatch { exactMatchCount += 1 }
            if containsMatch { answerContainsCount += 1 }
            if callsMatch && containsMatch { bothCount += 1 }

            let resultObj: [String: Any] = [
                "id": id,
                "calls": actualCalls,
                "answer": finalAnswer,
                "error": errorStr ?? NSNull(),
                "seconds": elapsed
            ]
            if let resultData = try? JSONSerialization.data(withJSONObject: resultObj),
               let resultLine = String(data: resultData, encoding: .utf8) {
                outStream += resultLine + "\n"
            }
        }

        try? outStream.write(toFile: outPath, atomically: true, encoding: .utf8)

        print("\n--- Summary ---")
        print("Exact Calls Match: \(exactMatchCount) / \(totalCount)")
        print("Answer Contains Match: \(answerContainsCount) / \(totalCount)")
        print("Both Match: \(bothCount) / \(totalCount)")
    }
}

await ToolBench.main()
