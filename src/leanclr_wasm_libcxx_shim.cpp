#include <cstddef>

#if defined(__EMSCRIPTEN__)
extern "C" std::size_t leanclr_godot_libcxx_hash_memory(const void* p_data, std::size_t p_size) noexcept
    __asm__("_ZNSt3__213__hash_memoryEPKvm");

extern "C" std::size_t leanclr_godot_libcxx_hash_memory(const void* p_data, std::size_t p_size) noexcept
{
    const unsigned char* bytes = static_cast<const unsigned char*>(p_data);
    std::size_t hash = 1469598103934665603ull;
    for (std::size_t i = 0; i < p_size; ++i)
    {
        hash ^= bytes[i];
        hash *= 1099511628211ull;
    }
    return hash;
}
#endif
