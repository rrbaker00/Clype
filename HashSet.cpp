#include "HashSet.h"

int HashMap::get_key(const std::string& value) {
	std::size_t key = 0;
	for (char c : value) {
		key += (key * 31) + int(c);
	}
	return int(key & 0x7FFFFFFF);
}

void HashMap::insert(const int& key, const std::string& value) {
	auto& bucket = h_bucket[key % h_bucket.size()];

	for (auto& item : bucket) {
		if (item.key == key) {
			item.value = value;
			return;
		}
	}
	bucket.push_back({ key, value});
	count++;
}

std::string HashMap::get_value(const int& key) const {
	const auto& bucket = h_bucket[key % h_bucket.size()];
	for (const auto& item : bucket) {
		if (item.key == key) { return item.value; }   
	}
	return "Not found";
}

bool HashMap::remove(const int& key) {
	auto& bucket = h_bucket[(key % h_bucket.size())];

	for (std::size_t i = 0; i < bucket.size(); ++i) {
		if (bucket[i].key == key) {
			if (i != bucket.size() - 1) {
				bucket[i] = std::move(bucket.back());
			}
			bucket.pop_back();
			count--;
			return true;
		}
	}
	return false;
}

void HashMap::test_time(const int& key, const std::string& value) {
	auto start_1 = std::chrono::high_resolution_clock::now();
	get_value(key);
	auto end_1 = std::chrono::high_resolution_clock::now();
	double timecmbnd_1 = std::chrono::duration_cast<std::chrono::nanoseconds>(end_1 - start_1).count();
	std::cout << timecmbnd_1 << std::endl;
}