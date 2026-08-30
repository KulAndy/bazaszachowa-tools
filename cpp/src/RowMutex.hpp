#ifndef ROW_MUTEX_H
#define ROW_MUTEX_H

#include <memory>
#include <mutex>
#include <unordered_map>

template <typename T> class RowMutexes {
public:
  std::shared_ptr<std::mutex> get(const T &id) {
    std::lock_guard<std::mutex> lock(mapMutex);

    auto &mutex = mutexes[id];

    if (!mutex) {
      mutex = std::make_shared<std::mutex>();
    }

    return mutex;
  }

private:
  std::mutex mapMutex;
  std::unordered_map<T, std::shared_ptr<std::mutex>> mutexes;
};

#endif // ROW_MUTEX_H
