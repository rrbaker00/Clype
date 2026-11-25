#include <iostream>
#include <vector>
#include <optional>
#include <string>
#include <utility>
#include <chrono>
#pragma once

class HashMap {
private:
	struct HashItem {
		int key;
		std::string value;
		HashItem(int k, std::string v) {
			key = k;
			value = v;
		}
	};
	std::vector<std::vector<HashItem>> h_bucket;
	std::size_t count = 0;
public:	
	HashMap() : h_bucket(20) {}

	int get_key(const std::string& value);

	void insert(const int& key, const std::string& value);

	std::string get_value(const int& key) const;

	void test_time(const int& key, const std::string& value);

	bool remove(const int& key);

	std::size_t size() const { return count; }

	void debugPrint() const {
		for (std::size_t i = 0; i < h_bucket.size(); ++i) {
			if (h_bucket[i].empty()) continue;
			std::cout << "bucket " << i << ": ";
			for (const auto& item : h_bucket[i]) {
				std::cout << "(" << item.key << ", " << item.value << ") ";
			}
			std::cout << "\n";
		}
		std::cout << "count = " << count << "\n";
	}
};


