import Foundation
import AVFoundation
import MusicUnderstanding

@main
struct CueciferAnalyzer {
    static func main() async throws {
        let args = CommandLine.arguments
        guard args.count >= 2 else {
            fputs("Usage: cuecifer-analyzer <path-to-flac-file-or-m3u>\n", stderr)
            exit(1)
        }
        
        let filePath = args[1]
        let fileURL = URL(fileURLWithPath: filePath)
        
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            fputs("Error: File does not exist at \(filePath)\n", stderr)
            exit(1)
        }
        
        let ext = fileURL.pathExtension.lowercased()
        if ext == "m3u" || ext == "m3u8" {
            try await processM3U(fileURL: fileURL)
        } else {
            try await processTrack(fileURL: fileURL, printToConsole: true)
        }
    }
    
    static func processM3U(fileURL: URL) async throws {
        let content = try String(contentsOf: fileURL, encoding: .utf8)
        let lines = content.components(separatedBy: .newlines)
        
        var trackURLs: [URL] = []
        let baseURL = fileURL.deletingLastPathComponent()
        
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty || trimmed.hasPrefix("#") { continue }
            
            let trackURL: URL
            if trimmed.hasPrefix("/") {
                trackURL = URL(fileURLWithPath: trimmed)
            } else {
                trackURL = baseURL.appendingPathComponent(trimmed)
            }
            trackURLs.append(trackURL)
        }
        
        print("Found \(trackURLs.count) tracks in M3U. Processing sequentially...")
        
        for trackURL in trackURLs {
            do {
                try await processTrack(fileURL: trackURL, printToConsole: false)
            } catch {
                print("Failed to process \(trackURL.lastPathComponent): \(error.localizedDescription)")
            }
        }
        
        print("Finished processing M3U.")
    }
    
    static func processTrack(fileURL: URL, printToConsole: Bool) async throws {
        let cachePath = fileURL.appendingPathExtension("cuecifer.json").path
        if FileManager.default.fileExists(atPath: cachePath) {
            if !printToConsole {
                print("Cache exists for \(fileURL.lastPathComponent). Skipping.")
            } else {
                // If single file and cached, just print it
                let data = try Data(contentsOf: URL(fileURLWithPath: cachePath))
                if let jsonString = String(data: data, encoding: .utf8) {
                    print(jsonString)
                }
            }
            return
        }
        
        let asset = AVURLAsset(url: fileURL)
        let session = try await MusicUnderstandingSession(asset: asset)
        
        let result = try await session.analyze(for: [.key, .rhythm, .pace, .structure, .instrumentActivity, .loudness])
        let encoder = JSONEncoder()
        encoder.outputFormatting = .prettyPrinted
        encoder.nonConformingFloatEncodingStrategy = .convertToString(positiveInfinity: "inf", negativeInfinity: "-inf", nan: "nan")
        let jsonData = try encoder.encode(result)
        
        try jsonData.write(to: URL(fileURLWithPath: cachePath))
        
        if printToConsole {
            if let jsonString = String(data: jsonData, encoding: .utf8) {
                print(jsonString)
            }
        } else {
            print("Successfully analyzed: \(fileURL.lastPathComponent)")
        }
    }
}
